import logging
import math

import gmsh
import numpy as np

from ews_fem_pipeline.prepare_simulation.model_settings import MeshParts
from ews_fem_pipeline.prepare_simulation.simulation_settings import Settings

logger = logging.getLogger(__name__)



mesh_parts = MeshParts()
settings = Settings()

gmsh.initialize()
gmsh.model.add("breast")
# Set option to save all elements in mesh
gmsh.option.setNumber("Mesh.SaveAll", 1)
# Set option to suppress all output of the mesher to the console.
gmsh.option.setNumber("General.Verbosity", 0)

# Dimension of object
dim0 = 0
dim1 = 1
dim2 = 2
dim3 = 3

# Rename objects to alias
build = gmsh.model.occ
mesh = gmsh.model.mesh

#############################
# Construct breast quadrant #
#############################

points = {}
lines = {}
loops = {}
surfs = {}

points[1] = build.addPoint(0, 0, 0, settings.model.mesh.ls, 1)  # Origin point
points[2] = build.addPoint(0, settings.model.geometry.radius, 0, settings.model.mesh.ls, 2)  # Point along rotation axis
points[3] = build.addPoint(0, 0, settings.model.geometry.radius, settings.model.mesh.ls,
                    3)  # Point perpendicular up to rotation axis

lines[1] = build.addCircleArc(points[2], points[1], points[3], 1)  # Lower circle arc of breast
lines[2] = build.addLine(points[3], points[1], 2)  # Line perpendicular up to rotation axis


# Get indices of all (including newly formed due to fragment) objects
all_points = build.getEntities(dim0)
all_lines = build.getEntities(dim1)
all_surfaces = build.getEntities(dim2)

# Name all points with convention p{tag}
for i in range(len(all_points)):
    idx = all_points[i][1]
    points[idx] = idx

# Name all lines with convention l{tag}
for i in range(len(all_lines)):
    idx = all_lines[i][1]
    lines[idx] = idx

#Form both halves of the breast by revolving around y-axis
build.revolve(all_lines[:], 0, 0, 0, 0, 1, 0, 1*math.pi)
build.revolve(all_lines[:], 0, 0, 0, 0, 1, 0, -1*math.pi)

#stretch out one half
all_surfaces = build.getEntities(dim2)
build.dilate(all_surfaces[2:], 0,0, 0, 1.5, 1,1)

#build underlying glandular tissue
glandular_surfaces = build.copy(all_surfaces[:])
all_surfaces = build.getEntities(dim2)
build.dilate(glandular_surfaces, 0, 1/2*settings.model.geometry.radius, 0, 0.7, 0.8, 0.7)

#fuse left and right halves (somehow does not form one mesh but does do something?)
build.fuse([all_surfaces[0], all_surfaces[1]], [all_surfaces[2], all_surfaces[3]], removeTool=True, removeObject=True)
build.fuse([all_surfaces[4], all_surfaces[5]], [all_surfaces[6], all_surfaces[7]], removeTool=True, removeObject=True)

build.synchronize()

# Alias for tissues. Only includes tissues, no nodes
tissues = mesh_parts.tissue_parts


### Construct and assign surfaces and volumes for different tissues ###

# Main glandular tissue
surfloop_gland = build.addSurfaceLoop([5,6,7,8])
test = build.addVolume([surfloop_gland], 1)
# Nipple and duct
duct = build.addCylinder(0,0.7*settings.model.geometry.radius,0,0,0.3*settings.model.geometry.radius+0.005,0,0.005, tag=2)
glandular_volume, _ = build.fuse([(3,1)], [(3,2)], removeObject=True, removeTool=True, tag=3)

#Surrounding adipose tissue
surfloop_adipose= build.addSurfaceLoop([1,2,3,4])
build.addVolume([surfloop_adipose], 4)

all_surfaces = build.getEntities(dim2)
all_volumes = build.getEntities(dim3)
#make sure tissue and skin does not overlap
build.fragment(all_volumes, all_surfaces)

adipose_volume, _ = build.cut([(3,4)], [(3,3)], removeObject=True, removeTool=False, tag=5)


build.synchronize()
all_final_surfaces = build.getEntities(dim2)
all_final_lines = build.getEntities(dim1)
all_final_volumes = build.getEntities(dim3)


tissues.adipose.tags = 5
tissues.glandular.tags = [6,7,8]

# Surface tags for skin and chest
tissues.skin.tags = [15,13, 22, 23]
tissues.chest.tags = [16,17]

#Remove lingering elements
build.remove(build.getEntities(dim2))
build.remove(build.getEntities(dim1))
build.remove(build.getEntities(dim0))

# Synchronize the geometry before assigning meshing
build.synchronize()

####################
# Generate 3D mesh #
####################

# Assign global mesh density by scaling mesh with length of mesh curves
curve_list = build.getEntities(dim1)
for curve in curve_list:
    length_curve = build.getMass(dim1, curve[1])
    mesh.setTransfiniteCurve(curve[1], int(settings.model.mesh.density * length_curve))

# Generate mesh up to 3D, set to predefined mesh order, and optionally optimize
mesh.generate(dim3)
mesh.setOrder(settings.model.mesh.order)
if settings.model.mesh.optimize:
    if settings.model.mesh.order == 1:
        mesh.optimize()
    else:
        mesh.optimize("HighOrder")

# Here we loop over the tissues and assign the nodes, elements, etc. to the different fields.
for name in tissues.model_fields:
    if getattr(tissues, name).dim == 2:  # noqa: PLR2004
        getattr(tissues, name).type = settings.model.mesh.elem_type_surface
    else:
        getattr(tissues, name).type = settings.model.mesh.elem_type_volume

    tags = getattr(tissues, name).tags

    if isinstance(tags, list):
        elements = []
        nodes = []
        for tag in tags:
            elements.append(mesh.getElements(getattr(tissues, name).dim, tag)[1][0])
            nodes.append(mesh.getElements(getattr(tissues, name).dim, tag)[2][0])
        elements = [int(item) for sublist in elements for item in sublist]
        nodes = np.array([int(item) for sublist in nodes for item in sublist])
        element_type = mesh.getElements(getattr(tissues, name).dim, tag)[0][0]
        num_nodes = int(mesh.getElementProperties(element_type)[3])
        getattr(tissues, name).elements = elements
        getattr(tissues, name).nodes = nodes.reshape(-1, num_nodes)
    else:
        element_type, elements, nodes = mesh.getElements(getattr(tissues, name).dim, getattr(tissues, name).tags)
        num_nodes = mesh.getElementProperties(element_type[0])[3]
        getattr(tissues, name).elements = elements[0]
        getattr(tissues, name).nodes = nodes[0].reshape(-1, num_nodes)

#########################################
# Extract all nodes and prep for output #
#########################################

# Get coordinates of nodes with their tag
node_tags, node_coords = gmsh.model.mesh.getNodes(returnParametricCoord=False)[0:2]
node_coords = np.reshape(node_coords, (-1, 3))

# The node Tags need to be properly ascending in the .feb file
sorted_ids = node_tags.argsort()
mesh_parts.nodes.tags = node_tags[sorted_ids]
mesh_parts.nodes.coords = node_coords[sorted_ids]
build.synchronize()
mesh.generate()

gmsh.write(r'C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\output\test.msh')
gmsh.finalize()


