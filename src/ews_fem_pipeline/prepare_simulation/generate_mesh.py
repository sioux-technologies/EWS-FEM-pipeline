import math
import numpy as np
import logging

import gmsh

from ews_fem_pipeline.prepare_simulation import MeshParts, Settings

logger = logging.getLogger(__name__)


def generate_mesh(settings: Settings()):
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

    p1 = build.addPoint(0, 0, 0, settings.model.mesh.ls, 1)  # Origin point
    p2 = build.addPoint(0, settings.model.geometry.radius, 0, settings.model.mesh.ls, 2)  # Point along rotation axis
    p3 = build.addPoint(0, 0, settings.model.geometry.radius, settings.model.mesh.ls,
                        3)  # Point perpendicular up to rotation axis

    l1 = build.addLine(p1, p2, 1)
    l2 = build.addCircleArc(p2, p1, p3, 2)  # Lower circle arc of breast
    l3 = build.addLine(p3, p1, 3)  # Line perpendicular up to rotation axis

    loop1 = build.addCurveLoop([l1, l2, l3], 1)
    s1 = build.addPlaneSurface([loop1], 1)

    p4 = build.addPoint(0, -settings.model.geometry.left_position_ellipse, 0, settings.model.mesh.ls, 4)
    p5 = build.addPoint(0, settings.model.geometry.radius + settings.model.geometry.position_nipple, 0, settings.model.mesh.ls, 5)
    p6 = build.addPoint(0, (settings.model.geometry.radius + settings.model.geometry.position_nipple - settings.model.geometry.left_position_ellipse) / 2,
                        -settings.model.geometry.position_center_ellipse,
                        settings.model.mesh.ls, 6)

    l4 = build.addEllipseArc(p4, p6, p5, p5, 4)
    l5 = build.addLine(p4, p5, 5)

    loop2 = build.addCurveLoop([l4, l5], 2)
    s2 = build.addPlaneSurface([loop2], 2)

    # Add back side breast
    p7 = build.addPoint(0, -settings.model.geometry.thickness_chest_wall, settings.model.geometry.radius, settings.model.mesh.ls, 7)
    p8 = build.addPoint(0, -settings.model.geometry.thickness_chest_wall, 0, settings.model.mesh.ls, 8)

    l6 = build.addLine(p3, p7, 6)
    l7 = build.addLine(p7, p8, 7)
    l8 = build.addLine(p8, p1, 8)

    loop3 = build.addCurveLoop(([l8, l3, l6, l7]))
    s3 = build.addPlaneSurface([loop3])

    # Fragment entire mesh in different regions (Assigns news points to intersection of curves)
    build.fragment([(dim2, s1), (dim2, s2)], [(dim2, s3)])

    # Get indices of all (including newly formed due to fragment) objects
    all_points = build.getEntities(dim0)
    all_lines = build.getEntities(dim1)
    all_surfaces = build.getEntities(dim2)

    # Name all points with convention p{tag}
    for i in range(len(all_points)):
        idx = all_points[i][1]
        globals()['p%s' % idx] = idx

    # Name all lines with convention l{tag}
    for i in range(len(all_lines)):
        idx = all_lines[i][1]
        globals()['l%s' % idx] = idx

    # Remove all surfaces as we will be rebuilding them
    build.remove(all_surfaces)
    # Remove all points that we will not need anymore. Note, first we remove the lines, then the points,
    # as lines are constructed by connecting points
    build.remove(
        [(dim1, l3), (dim1, l4), (dim1, l5), (dim1, l7), (dim1, l8), (dim1, l9), (dim1, l11), (dim1, l12),
         (dim1, l14)])
    build.remove([(dim0, p6), (dim0, p10), (dim0, p12), (dim0, p14)])

    # Add lines to complete reconstruction
    l3 = build.addLine(p16, p13, 3)
    l4 = build.addLine(p8, p15, 4)

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
        if getattr(tissues, name).dim == 2:
            getattr(tissues, name).type = settings.model.mesh.elem_type_surface
        else:
            getattr(tissues, name).type = settings.model.mesh.elem_type_volume

        tags = getattr(tissues, name).tags

        if type(tags) == list:
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
