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
    if settings.model.geometry.angle_nipple != 0:
        build.addCylinder(0, -(1 / 2 * settings.model.geometry.radius_breast / np.sin(
            1 / 2 * settings.model.geometry.angle_nipple / 180 * math.pi)), -0.2,
                          0, 0, 0.4,
                          (1 / 2 * settings.model.geometry.radius_breast / np.sin(
                              1 / 2 * settings.model.geometry.angle_nipple / 180 * math.pi)), tag=2)
    else:
        build.addBox(-0.5, 0, -0.5, 1, -1, 1, tag = 2)

    # Build glandular tissue by copying and downscaling breast volume
    build.copy([(3, 1)])  # tag = 3
    build.dilate([(3, 3)], 0, 1 / 2 * settings.model.geometry.radius_breast, 0,
                 settings.model.geometry.scaling_factor_glandular, settings.model.geometry.scaling_factor_glandular,
                 settings.model.geometry.scaling_factor_glandular)

    # Cut torso from breast shape
    build.cut([(3, 1)], [(3, 2)], removeTool=False)
    # Move and cut torso from glandular tissue to ensure a stable layer of adipose tissue on chest
    build.translate([(3, 2)], 0,
                    (1 / 2 * (
                    1 - settings.model.geometry.scaling_factor_glandular)) * settings.model.geometry.radius_breast,
                    0)
    build.cut([(3, 3)], [(3, 2)], removeTool=True)

    # Add duct and nipple as a cylinder
    build.addSphere(0, settings.model.geometry.radius_breast, 0, settings.model.geometry.radius_nipple, tag=6)
    build.addCylinder(0, settings.model.geometry.radius_breast - 0.04, 0, 0, 0.04,
                      0, settings.model.geometry.radius_nipple, tag=4)
    # Fuse duct/nipple with glandular tissue
    build.fuse([(3, 3)], [(3, 4), (3,6)], tag=5)
    # Separate glandular from adipose tissue
    build.cut([(3, 1)], [(3, 5)], removeTool=False)

    all_surfaces = build.getEntities(dim=2)
    all_volumes = build.getEntities(dim=3)

    # Fragment full model. Ensures no surfaces and volumes overlap. Note: replaces all tags!
    build.fragment(all_volumes, all_surfaces)

    assign_tissues(build, mesh_parts)

    # Remove lingering elements
    build.remove(build.getEntities(dim=2))
    build.remove(build.getEntities(dim=1))
    build.remove(build.getEntities(dim=0))

    # Synchronize the geometry before assigning meshing
    build.synchronize()


def assign_tissues(build, mesh_parts: MeshParts):
    # Alias for tissues. Only includes tissues, no nodes
    tissues = mesh_parts.tissue_parts

    # Construct and assign surfaces and volumes for different tissues ###
    all_final_volumes = build.getEntities(dim=3)
    adipose = all_final_volumes[0][1]
    glandular = all_final_volumes[1][1]
    tissues.adipose.tags = [adipose]
    tissues.glandular.tags = [glandular]

    # Surface tags for skin and chest
    adipose_surfs = build.getSurfaceLoops(adipose)[1][0]
    glandular_surfs = build.getSurfaceLoops(glandular)[1][0]
    outer_surfaces = np.setdiff1d(adipose_surfs, glandular_surfs)
    nipple_surfaces = list(np.setdiff1d(glandular_surfs, adipose_surfs))
    tissues.skin.tags = [outer_surfaces[0]] + nipple_surfaces
    tissues.chest.tags = [outer_surfaces[1]]


def construct_bspline_points(build, settings: Settings, n_points_u: int, n_points_v: int) -> np.ndarray[Any, np.dtype[np.int_]]:
    # Points for the breast surface are generated on circle arcs with variable radius to create asymmetry
    # 3/4 of a "sphere" are generated, this will be cut down later

    # Initialize array for saving points
    surface_control_points = np.empty((n_points_u, n_points_v), dtype=int)

    # Rotate around the y-axis
    for i, theta in enumerate(np.linspace(0, 2 * math.pi, n_points_u), start=1):
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


def build_mesh(mesh, tissues: TissueParts, settings: Settings):
    ####################
    # Generate 3D mesh #
    ####################

    # Assign global mesh density by scaling mesh with length of mesh curves
    curve_list = gmsh.model.occ.getEntities(dim=1)
    for curve in curve_list:
        length_curve = gmsh.model.occ.getMass(dim=1, tag=curve[1])
        mesh.setTransfiniteCurve(curve[1], int(settings.model.mesh.density * length_curve))

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

