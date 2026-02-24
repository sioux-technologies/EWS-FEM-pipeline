import logging
import math

import gmsh
import numpy as np

from ews_fem_pipeline.prepare_simulation.model_settings import MeshParts
from ews_fem_pipeline.prepare_simulation.simulation_settings import Settings

logger = logging.getLogger(__name__)



mesh_parts = MeshParts()
settings = Settings()
radius_nipple = 0.005
thickness_adipose = 0.01
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

radius_arc1 = settings.model.geometry.radius-radius_nipple
points[1] = build.addPoint(0, 0, 0, settings.model.mesh.ls, 1)  # Origin point
points[2] = build.addPoint(0, radius_arc1, 0, settings.model.mesh.ls, 2)  # Point along rotation axis

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

circle_points = {}
top_points = {}
bottom_points = {}
circle_arcs = {}
bottom_circle_lines = {}
top_circle_lines = {}
n_points = 20


for i, theta in enumerate(np.linspace(0, 2*math.pi, n_points, endpoint=False), start=1):
    radius_var = radius_arc1 * (1+ 1/8*(np.cos(theta)+1) + 1/32*np.cos(3*theta))
    bottom_points[i] = build.addPoint(radius_nipple*np.cos(theta),
                radius_arc1-(radius_var/(np.sin(2*np.arctan(radius_arc1/radius_var)))),
                radius_nipple*np.sin(theta), settings.model.mesh.ls)
    circle_points[i] = build.addPoint((radius_var+radius_nipple)*np.cos(theta), 0, (radius_var+radius_nipple)*np.sin(theta), settings.model.mesh.ls)
    top_points[i] = build.addPoint(radius_nipple*np.cos(theta), radius_arc1, radius_nipple*np.sin(theta))
for i in range(1, n_points+1):
    circle_arcs[i] = build.addCircleArc(top_points[i], bottom_points[i], circle_points[i])
    top_circle_lines[i] = build.addLine(top_points[i], top_points[(i%n_points+1)])
all_points = build.getEntities(dim0)
bottom_circle_lines = build.addSpline(list(circle_points.values())+[circle_points[1]])
bottom_circle_lines, _ = build.fragment([(1, bottom_circle_lines)], all_points)
bottom_circle_lines = np.array(bottom_circle_lines)[np.where(np.array(bottom_circle_lines)[:, 0] == 1), 1][0]

for i in range(1, n_points+1):
    loop = build.addCurveLoop([circle_arcs[i], top_circle_lines[i], circle_arcs[(i)%n_points+1], bottom_circle_lines[i-1]])
    surf = build.addSurfaceFilling(loop)

all_points = build.getEntities(dim0)
build.remove(all_points) #remove bottom circle points and other unattached points

bottom_surf = build.addCurveLoop(bottom_circle_lines)
bottom_surf = build.addPlaneSurface([bottom_surf]) #n = n_points + 1

nipple_surf = build.addCurveLoop(list(top_circle_lines.values()))
nipple_surf = build.addPlaneSurface([nipple_surf]) #n = n_points + 2

surfloop_adipose = build.addSurfaceLoop(list(range(1,n_points+3)))
build.addVolume([surfloop_adipose], tag = 3)

scaling_factor = 1-(thickness_adipose/radius_arc1)
build.copy([(3,3)]) #tag = 4
build.dilate([(3,4)], 0,1/2*radius_arc1, 0, scaling_factor, scaling_factor, scaling_factor)
build.addCylinder(0,radius_arc1-0.02, 0, 0, 0.025, 0, radius_nipple, tag = 5)
build.fuse([(3,5)], [(3,4)], tag = 6) #fuse duct/nipple with glandular tissue
build.cut([(3,3)], [(3,6)], removeTool= False)

all_surfaces = build.getEntities(dim2)
all_volumes = build.getEntities(dim3)

build.fragment(all_volumes, all_surfaces)
# Alias for tissues. Only includes tissues, no nodes
tissues = mesh_parts.tissue_parts

# Construct and assign surfaces and volumes for different tissues ###
all_final_surfaces = build.getEntities(dim2)
all_final_lines = build.getEntities(dim1)
all_final_volumes = build.getEntities(dim3)

tissues.adipose.tags = [all_final_volumes[0][1]]
tissues.glandular.tags = [all_final_volumes[1][1]]

# Surface tags for skin and chest
tissues.skin.tags = [46, 48] + list(range(50, 68))
tissues.chest.tags = [49]

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


gmsh.write(r'C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\output\test.msh')
gmsh.finalize()


