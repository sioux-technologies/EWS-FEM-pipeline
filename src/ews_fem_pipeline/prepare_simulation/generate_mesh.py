import logging
import math
from typing import Any
import gmsh
import numpy as np


from ews_fem_pipeline.prepare_simulation.model_settings import MeshParts, TissueParts
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

    # Rename objects to alias
    build_geometry(gmsh.model.occ, mesh_parts, settings)
    build_mesh(gmsh.model.mesh, mesh_parts.tissue_parts, settings)
    prep_for_output(mesh_parts)

    gmsh.finalize()

    return mesh_parts

def build_geometry(build, mesh_parts: MeshParts, settings: Settings):
    #############################
    # Construct breast surface  #
    #############################
    surface_control_points = construct_bspline_points(build, settings, 17, 8)
    # Define knots and multiplicities for closed surface
    knots = np.linspace(0, 1, 17+2)
    mults = np.concatenate(([2], np.ones(17), [2]))
    # Build breast surface
    build.addBSplineSurface(surface_control_points.flatten(order='F'), len(surface_control_points), knotsU=knots,
                            multiplicitiesU=mults,
                            degreeU=2)
    # Build breast volume
    build.addCurveLoop([3], tag=2)
    build.addSurfaceFilling(2, tag=2)
    build.addSurfaceLoop([1, 2], tag=1)
    build.addVolume([1], tag=1)

    # remove control points
    build.remove(build.getEntities(dim=0))

    # Build shape of torso
    build.addCylinder(0, -(1 / 2 * settings.model.geometry.radius_breast / np.sin(
        1 / 2 * settings.model.geometry.angle_nipple / 180 * math.pi)), -0.2,
                      0, 0, 0.4,
                      (1 / 2 * settings.model.geometry.radius_breast / np.sin(
                          1 / 2 * settings.model.geometry.angle_nipple / 180 * math.pi)), tag=2) #curved surfacetag = 12

    # Build glandular tissue by copying and downscaling breast volume
    build.copy([(3, 1)])  # tag = 3
    build.dilate([(3, 3)], 0, 0, 0,
                 settings.model.geometry.scaling_factor_glandular_xz, settings.model.geometry.scaling_factor_glandular_y,
                 settings.model.geometry.scaling_factor_glandular_xz)

    # Create a surface at distance  ~1 element from the chest, this is used later for meshing purposes
    # make sure the space between this layer and the glandular tissue is large enough
    if settings.model.geometry.thickness_chest_wall > 0.004:
        thickness_layer1 = 0.002
    else:
        thickness_layer1 = settings.model.geometry.thickness_chest_wall

    scaling_layer = 1-(thickness_layer1/settings.model.geometry.radius_breast)
    build.copy([(3, 1)])  # tag = 4
    build.dilate([(3, 4)], 0, 0, 0, scaling_layer, scaling_layer, scaling_layer)

    # Cut torso from breast shape
    build.cut([(3, 1)], [(3, 2)], removeTool=False)

    # Get the mid-layer surface by intersection of the torso and the mid-volume
    build.translate([(3, 2)], 0, thickness_layer1, 0)
    build.intersect([(3,4)], [(2, 12)], removeObject = True, removeTool=False) #surftag = 15

    # Cut torso shape from glandular, forming an even layer of adipose tissue between chest and glandular
    # Currently does not work for chest wall thickness < 0.004!!!
    # Also remove the torso shape
    if thickness_layer1 != settings.model.geometry.thickness_chest_wall:
        build.translate([(3, 2)], 0, settings.model.geometry.thickness_chest_wall - thickness_layer1, 0)
    build.cut([(3, 3)], [(3, 2)], removeTool=True)

    # Build the mid-layer volume
    build_meshlayer(build)

    # Add duct and nipple as a cylinder
    build.addCylinder(0, settings.model.geometry.radius_breast - 0.04, 0, 0, 0.035,
                      0, settings.model.geometry.radius_nipple, tag=6)
    build.addSphere(0, settings.model.geometry.radius_breast-0.005, 0, settings.model.geometry.radius_nipple, tag=7)

    # Fuse duct/nipple with glandular tissue
    build.fuse([(3, 3)], [(3, 7), (3,6)], tag=8)
    # Separate glandular from adipose tissue
    build.cut([(3, 1)], [(3, 8)], removeTool=False)


    # Remove lingering elements
    build.remove(build.getEntities(dim=2))
    build.remove(build.getEntities(dim=1))
    build.remove(build.getEntities(dim=0))

    # Fragment full model. Ensures no surfaces and volumes overlap. Note: replaces all tags!
    all_surfaces = build.getEntities(dim=2)
    all_volumes = build.getEntities(dim=3)
    build.fragment(all_volumes, all_surfaces)


    assign_tissues(build, mesh_parts.tissue_parts, settings)
    # Synchronize the geometry before assigning meshing
    build.synchronize()

def construct_bspline_points(build, settings: Settings, n_points_u: int, n_points_v: int) -> np.ndarray[Any, np.dtype[np.int_]]:
    # Points for the breast surface are generated on circle arcs with variable radius to create asymmetry
    # 3/4 of a "sphere" are generated, this will be cut down later

    # Initialize array for saving points
    surface_control_points = np.empty((n_points_u, n_points_v), dtype=int)

    # Rotate around the y-axis
    for i, theta in enumerate(np.linspace(0, 2 * math.pi, n_points_u), start=1):
        theta = theta - 1/(2*n_points_u)*2*math.pi
        radius_var = settings.model.geometry.radius_breast * (1 + settings.model.geometry.asym_p1 * (np.cos(theta) + 1)
                                                              + settings.model.geometry.asym_p2 * (
                                                                      np.cos(2 * theta) + 1)
                                                              + settings.model.geometry.asym_p3 * (
                                                                      np.cos(3 * theta) + 1))
        # the points are placed on a circle arc with a radius radius_extra > radius_var
        radius_extra = radius_var / (np.sin(2 * np.arctan(settings.model.geometry.radius_breast / radius_var)))
        for j, phi in enumerate(np.linspace(start=0, stop=np.pi, num=n_points_v, endpoint=False)):
            surface_control_points[i - 1, j] = build.addPoint(radius_extra * np.cos(theta) * np.sin(phi),
                                                              radius_extra * np.cos(
                                                                  phi) + settings.model.geometry.radius_breast - radius_extra,
                                                              radius_extra * np.sin(theta) * np.sin(phi))

    # Close the loop
    surface_control_points = np.concatenate((surface_control_points, surface_control_points[1, :].reshape(1, -1)),
                                            axis=0)

    return surface_control_points

def build_meshlayer(build):
    # Define curves of surfaces of chest wall (surftag 11) and new mid-layer (surftag 15)
    curve1 = build.getCurveLoops(11)[1][0][0]
    curve2 = build.getCurveLoops(15)[1][0][0]

    # Split the base curves in two to create the connection between the base surfaces in two parts
    plane = build.addRectangle(-0.2, -0.2, 0, 0.2, 0.4, tag=0)
    fragmented = build.fragment([(1, curve1), (1, curve2)], [(2, plane)], removeObject=False, removeTool=True)
    build.remove([(2, 0)], recursive=True)

    # Add two lines connecting the two surfaces
    sideline1 = build.addLine(149, 146)
    sideline2 = build.addLine(152, 153)

    # Define both halves of the connecting surface
    curveloop1 = build.addCurveLoop([fragmented[1][0][0][1], sideline1, fragmented[1][1][0][1], sideline2])
    curveloop2 = build.addCurveLoop([fragmented[1][0][1][1], sideline1, fragmented[1][1][1][1], sideline2])
    sidesurf1 = build.addBSplineFilling(curveloop1)
    sidesurf2 = build.addBSplineFilling(curveloop2)
    connecting_curves = build.addWire([fragmented[1][1][0][1], fragmented[1][1][1][1]])
    connecting_surf = build.addTrimmedSurface(15, [connecting_curves], wire3D=True)
    build.fuse([(2, sidesurf1), (2, sidesurf2), (2, 11)],
               [(2, connecting_surf)])  # does not change tags, does fix adjacency
    # Add layer as new volume and separate from main adipose tissue
    build.addVolume([build.addSurfaceLoop([sidesurf1, sidesurf2, 11, connecting_surf], sewing=False)], tag=4)
    build.cut([(3, 1)], [(3, 4)], removeTool=False)


def assign_tissues(build, tissues: TissueParts, settings: Settings):
    # Construct and assign surfaces and volumes for different tissues ###
    all_final_volumes = build.getEntities(dim=3)
    adipose = [all_final_volumes[0][1], all_final_volumes[1][1]]
    glandular = [all_final_volumes[2][1]]
    tissues.adipose.tags = adipose
    tissues.glandular.tags = glandular

    # Surface tags for skin and chest
    adipose_surfs = list(np.concatenate((build.getSurfaceLoops(adipose[0])[1][0], build.getSurfaceLoops(adipose[1])[1][0])))
    glandular_surfs = list(build.getSurfaceLoops(glandular[0])[1][0])
    all_surfs, counts = np.unique(adipose_surfs+glandular_surfs, return_counts = True)
    outer_surfaces = all_surfs[counts == 1]
    if settings.model.geometry.thickness_chest_wall > 0.004:
        tissues.skin.tags = [outer_surfaces[1]]
        tissues.chest.tags = [outer_surfaces[0]]
    else:
        tissues.skin.tags = [outer_surfaces[0]]
        tissues.chest.tags = [outer_surfaces[1]]




def build_mesh(mesh, tissues: TissueParts, settings: Settings):
    ####################
    # Generate 3D mesh #
    ####################
    zbound = np.abs(gmsh.model.getBoundingBox(2, tissues.skin.tags[0])[2])
    size_max = settings.model.mesh.ls
    gmsh.model.mesh.field.add("Box", 1)
    gmsh.model.mesh.field.setNumber(1, 'VOut', size_max)
    gmsh.model.mesh.field.add("MathEval", 2)
    gmsh.model.mesh.field.setString(2, "F",
                                    f"{size_max}/{np.abs(zbound)/2}*(z+{zbound})+0.003")
    gmsh.model.mesh.field.add("Min", 3)
    gmsh.model.mesh.field.setNumbers(3, "FieldsList", [1,2])
    gmsh.model.mesh.field.setAsBackgroundMesh(3)

    gmsh.option.setNumber("Mesh.MeshSizeExtendFromBoundary", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromPoints", 0)
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature", 0)

    gmsh.option.setNumber("Mesh.Algorithm", 5)
    # Generate mesh up to 3D, set to predefined mesh order, and optionally optimize
    mesh.generate(dim=3)
    mesh.setOrder(settings.model.mesh.order)
    if settings.model.mesh.optimize:
        if settings.model.mesh.order == 1:
            mesh.optimize()
        else:
            mesh.optimize("HighOrder")

    # Here we loop over the tissues and assign the nodes, elements, etc. to the different fields.
    for name in TissueParts.model_fields:
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

def prep_for_output(mesh_parts: MeshParts):
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

