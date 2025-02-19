import logging
import math

import gmsh
import numpy as np

from ews_fem_pipeline.prepare_simulation.model_settings import MeshParts
from ews_fem_pipeline.prepare_simulation.simulation_settings import Settings

logger = logging.getLogger(__name__)


def generate_mesh(settings: Settings) -> MeshParts:
    """
    In this function, the mesh is generated from settings extracted from the Settings class, in particular the mesh
    and geometry classes. These settings are explained in detail in model_settings.py under the MeshSettings and GeometrySettings
    classes.
    """

    mesh_parts = MeshParts()

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

    lines[1] = build.addLine(points[1], points[2], 1)
    lines[2] = build.addCircleArc(points[2], points[1], points[3], 2)  # Lower circle arc of breast
    lines[3] = build.addLine(points[3], points[1], 3)  # Line perpendicular up to rotation axis

    loops[1] = build.addCurveLoop([lines[1], lines[2], lines[3]], 1)
    surfs[1] = build.addPlaneSurface([loops[1]], 1)

    points[4] = build.addPoint(0, -settings.model.geometry.left_position_ellipse, 0, settings.model.mesh.ls, 4)
    points[5] = build.addPoint(0, settings.model.geometry.radius + settings.model.geometry.position_nipple, 0, settings.model.mesh.ls, 5)
    points[6] = build.addPoint(0, (settings.model.geometry.radius + settings.model.geometry.position_nipple - settings.model.geometry.left_position_ellipse) / 2,
                        -settings.model.geometry.position_center_ellipse,
                        settings.model.mesh.ls, 6)

    lines[4] = build.addEllipseArc(points[4], points[6], points[5], points[5], 4)
    lines[5] = build.addLine(points[4], points[5], 5)

    loops[2] = build.addCurveLoop([lines[4], lines[5]], 2)
    surfs[2] = build.addPlaneSurface([loops[2]], 2)

    # Add back side breast
    points[7] = build.addPoint(0, -settings.model.geometry.thickness_chest_wall, settings.model.geometry.radius, settings.model.mesh.ls, 7)
    points[8] = build.addPoint(0, -settings.model.geometry.thickness_chest_wall, 0, settings.model.mesh.ls, 8)

    lines[6] = build.addLine(points[3], points[7], 6)
    lines[7] = build.addLine(points[7], points[8], 7)
    lines[8] = build.addLine(points[8], points[1], 8)

    loops[3] = build.addCurveLoop(([lines[8], lines[3], lines[6], lines[7]]))
    surfs[3] = build.addPlaneSurface([loops[3]])

    # Fragment entire mesh in different regions (Assigns news points to intersection of curves)
    build.fragment([(dim2, surfs[1]), (dim2, surfs[2])], [(dim2, surfs[3])])

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

    # Remove all surfaces as we will be rebuilding them
    build.remove(all_surfaces)
    # Remove all points that we will not need anymore. Note, first we remove the lines, then the points,
    # as lines are constructed by connecting points
    build.remove([
        (dim1, lines[3]),
        (dim1, lines[4]),
        (dim1, lines[5]),
        (dim1, lines[7]),
        (dim1, lines[8]),
        (dim1, lines[9]),
        (dim1, lines[11]),
        (dim1, lines[12]),
        (dim1, lines[14]),
    ])
    build.remove([
        (dim0, points[6]),
        (dim0, points[10]),
        (dim0, points[12]),
        (dim0, points[14]),
    ])

    # Add lines to complete reconstruction
    lines[3] = build.addLine(points[16], points[13], 3)
    lines[4] = build.addLine(points[8], points[15], 4)

    ###############################################
    # Construct 3D geometry by revolving quadrant #
    ###############################################

    # Get all lines and revolves around major axis
    all_current_lines = build.getEntities(dim1)
    build.revolve(all_current_lines, 0, 0, 0, 0, 1, 0, 2 * math.pi)

    # Alias for tissues. Only includes tissues, no nodes
    tissues = mesh_parts.tissue_parts

    # Construct and assign surfaces and volumes for different tissues
    surfloop_gland = build.addSurfaceLoop([1, 2, 5])
    surfloop_fat = build.addSurfaceLoop([1, 2, 3, 4, 6])

    # Surface tags for skin and chest
    tissues.skin.tags = [9, 10]
    tissues.chest.tags = 11
    tissues.glandular.tags = build.addVolume([surfloop_gland])
    tissues.adipose.tags = build.addVolume([surfloop_fat])

    # Remove lingering elements
    build.fragment([(dim3, 1)], [(dim3, 2)])
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

    gmsh.finalize()

    return mesh_parts
