"""Gmsh-based source-case mesh generation.

The COMSOL builder mainly uses analytical geometry, but this module still
exports mesh/lobule artefacts that document the resolved source-case anatomy.
"""

import math
import numpy as np
import logging

import gmsh

from ews_fem_pipeline_comsol.source_case import MeshParts, Settings
from ews_fem_pipeline_comsol.source_case.lobule_generation import visualize_lobules_2d

logger = logging.getLogger(__name__)


def _existing_entities(prefix: str, ids: list[int], dim: int):
    entities = []
    for idx in ids:
        if f"{prefix}{idx}" in globals():
            entities.append((dim, globals()[f"{prefix}{idx}"]))
    return entities


def _find_point_tag(point_coords: dict[int, tuple[float, float, float]], predicate):
    for tag, coords in point_coords.items():
        if predicate(coords):
            return tag
    raise ValueError("Could not resolve required point after gmsh fragment.")


def _resolve_rebuild_lines(build, thickness_chest_wall: float):
    """
    Resolve the two reconnect lines after the 2D fragment/remove cleanup step.

    Older versions relied on fixed gmsh OCC point tags (`p13/p15/p16`), which
    breaks as soon as the side profile construction changes. Instead, detect the
    dangling endpoints from the surviving line set and reconnect them based on
    their geometric position.
    """
    build.synchronize()
    current_lines = build.getEntities(1)
    degree = {}

    for _, line_tag in current_lines:
        for _, pt_tag in gmsh.model.getBoundary([(1, line_tag)], combined=False, oriented=False):
            degree[pt_tag] = degree.get(pt_tag, 0) + 1

    dangling = [pt_tag for pt_tag, count in degree.items() if count == 1]
    coords = {pt: tuple(gmsh.model.getValue(0, pt, [])) for pt in dangling}
    tol = 1e-6

    posterior_pair = [
        pt for pt, xyz in coords.items()
        if abs(xyz[1] + thickness_chest_wall) < tol
    ]
    if len(posterior_pair) != 2:
        raise RuntimeError("Failed to resolve posterior reconnect pair after cleanup")

    posterior_pair = sorted(posterior_pair, key=lambda pt: coords[pt][2])

    # Legacy symmetric geometry tends to leave 4 dangling points: two posterior
    # and two anterior. With explicit nipple-tip stabilization, gmsh can keep
    # the anterior reconnect line already present, leaving only one anterior
    # dangling point plus one branching point of degree 3.
    if len(dangling) == 4:
        anterior_pair = [pt for pt in dangling if pt not in posterior_pair]
        if len(anterior_pair) != 2:
            raise RuntimeError("Failed to resolve anterior reconnect pair after cleanup")
        anterior_pair = sorted(anterior_pair, key=lambda pt: coords[pt][1])
        return {
            "posterior_lower": posterior_pair[0],
            "posterior_upper": posterior_pair[1],
            "anterior_lower": anterior_pair[0],
            "anterior_upper": anterior_pair[1],
            "anterior_already_connected": False,
        }

    if len(dangling) == 3:
        branch_points = [pt for pt, count in degree.items() if count == 3]
        anterior_pair = [pt for pt in dangling if pt not in posterior_pair]
        if len(branch_points) != 1 or len(anterior_pair) != 1:
            raise RuntimeError("Failed to resolve mixed reconnect topology after cleanup")
        return {
            "posterior_lower": posterior_pair[0],
            "posterior_upper": posterior_pair[1],
            "anterior_lower": branch_points[0],
            "anterior_upper": anterior_pair[0],
            "anterior_already_connected": True,
        }

    raise RuntimeError(f"Expected 3 or 4 dangling points after cleanup, found {len(dangling)}")


def _classify_external_surfaces():
    """
    Resolve external skin and chest-support surfaces without relying on fixed OCC tags.

    External surfaces are those adjacent to exactly one volume. Chest surfaces are
    the external surfaces whose bounding box stays on the posterior side
    (`y_max <= 0` within a small tolerance). Remaining external surfaces are
    treated as skin.
    """
    chest_tags = []
    skin_tags = []
    external_surfaces = []
    tol = 1e-6

    for _, surf_tag in gmsh.model.getEntities(2):
        up, _ = gmsh.model.getAdjacencies(2, surf_tag)
        if len(up) != 1:
            continue
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, surf_tag)
        external_surfaces.append(
            {
                "tag": surf_tag,
                "xmin": xmin,
                "ymin": ymin,
                "zmin": zmin,
                "xmax": xmax,
                "ymax": ymax,
                "zmax": zmax,
            }
        )
        if ymax <= tol:
            chest_tags.append(surf_tag)
        else:
            skin_tags.append(surf_tag)

    if not chest_tags and external_surfaces:
        # Mild profile-asymmetry and support-shape changes can leave the most
        # posterior support surface with a tiny positive ymax, which defeats the
        # strict `ymax <= 0` rule even though the posterior support is still
        # geometrically present. Fall back to the most posterior external
        # surfaces by selecting the smallest ymax group.
        min_ymax = min(item["ymax"] for item in external_surfaces)
        fallback_tol = max(5e-5, abs(min_ymax) * 0.05)
        chest_tags = [
            item["tag"]
            for item in external_surfaces
            if item["ymax"] <= min_ymax + fallback_tol
        ]
        skin_tags = [
            item["tag"]
            for item in external_surfaces
            if item["tag"] not in chest_tags
        ]

    return skin_tags, chest_tags


def _build_outer_profile_curve(build, settings, origin_tag, front_tag, pole_tag):
    """
    Build the anterior outer contour for the revolved axisymmetric source profile.

    The default path preserves the legacy circular arc exactly. Stage-1 geometry
    refactoring can opt into an elliptical arc to increase anterior projection
    and/or superior pole height without touching the downstream source-case/COMSOL
    separation.
    """
    geometry = settings.model.geometry

    if (
        not geometry.profile_asymmetry_enabled
        and geometry.inferior_fullness_ratio == 0.0
        and geometry.superior_flattening_ratio == 0.0
        and geometry.nipple_projection_ratio == 0.0
        and
        geometry.outer_profile_mode == "circular"
        and geometry.anterior_projection_scale == 1.0
        and geometry.superior_pole_scale == 1.0
        and geometry.upper_pole_projection_ratio == 0.0
    ):
        return build.addCircleArc(front_tag, origin_tag, pole_tag, 2)

    if geometry.profile_asymmetry_enabled or geometry.nipple_projection_ratio > 0.0:
        # Use two controls so the front extent stays visually present while the
        # superior pole becomes slightly flatter and less perfectly circular.
        control1_tag = build.addPoint(
            0,
            geometry.outer_front_position,
            max(geometry.nipple_transition_height, geometry.outer_pole_height * 0.10),
            settings.model.mesh.ls,
            102,
        )
        control2_tag = build.addPoint(
            0,
            geometry.outer_front_position * max(0.34, 0.58 - 0.40 * geometry.superior_flattening_ratio),
            geometry.outer_pole_height * 0.84,
            settings.model.mesh.ls,
            103,
        )
        return build.addSpline([front_tag, control1_tag, control2_tag, pole_tag], 2)

    major_tag = front_tag
    if geometry.outer_pole_height > geometry.outer_front_position:
        major_tag = pole_tag

    return build.addEllipseArc(front_tag, origin_tag, major_tag, pole_tag, 2)


def _build_lower_profile_curve(build, settings, base_tag, front_tag):
    """
    Build the lower/anterior profile from chest base to nipple/front.

    Stage 4 uses this to introduce a controlled superior-inferior profile
    asymmetry while still keeping the full model axisymmetric in 3D.
    """
    geometry = settings.model.geometry

    if not geometry.profile_asymmetry_enabled and geometry.nipple_projection_ratio == 0.0:
        return build.addLine(base_tag, front_tag, 1)

    # First stabilize the anterior tip itself. A simple two-control transition
    # keeps the front/nipple region visible without immediately introducing a
    # strong lower-pole reshaping that can collapse the fragment topology.
    if geometry.inferior_fullness_ratio <= 0.0:
        control_tag = build.addPoint(
            0,
            geometry.outer_front_position,
            max(0.25 * geometry.nipple_transition_height, geometry.outer_pole_height * 0.02),
            settings.model.mesh.ls,
            104,
        )
        return build.addSpline([base_tag, control_tag, front_tag], 1)

    control1_tag = build.addPoint(
        0,
        geometry.outer_front_position * max(0.22, 0.42 * geometry.inferior_fullness_ratio),
        geometry.outer_pole_height * 0.06,
        settings.model.mesh.ls,
        101,
    )
    control2_tag = build.addPoint(
        0,
        geometry.outer_front_position,
        max(0.25 * geometry.nipple_transition_height, geometry.outer_pole_height * 0.02),
        settings.model.mesh.ls,
        104,
    )
    return build.addSpline([base_tag, control1_tag, control2_tag, front_tag], 1)


def _build_posterior_support_curve(build, settings, top_tag, bottom_tag):
    """
    Build a light curved posterior support boundary.

    This is intentionally lighter than a full explicit torso/pectoralis model.
    It curves the posterior chest-support wall so the side-view reads closer to
    a shallow thorax arc while keeping the inner breast attachment topology
    stable for the legacy gmsh construction.
    """
    geometry = settings.model.geometry

    if geometry.posterior_curve_depth <= 0.0:
        return build.addLine(top_tag, bottom_tag, 7)

    control_tag = build.addPoint(
        0,
        -geometry.thickness_chest_wall - geometry.posterior_curve_depth,
        0.5 * geometry.posterior_support_height,
        settings.model.mesh.ls,
    )
    return build.addSpline([top_tag, control_tag, bottom_tag], 7)


def _add_pectoralis_volume(build, settings, dim3: int):
    """
    Add a separate ellipsoidal pectoralis-lite volume behind the breast.

    The volume is intended to be carved out of the adipose domain so it can act
    as a real support domain in later source-case runs, while still being simple
    enough for stage-3A experimentation.
    """
    geometry = settings.model.geometry

    if geometry.pectoralis_support_projection <= 0.0:
        return None

    z_center = geometry.pectoralis_support_center_height
    z_span = max(0.006, 1.1 * geometry.pectoralis_support_span_height)
    x_span = max(0.02, 1.25 * geometry.radius)
    y_span = max(0.0012, 1.6 * geometry.pectoralis_support_projection)

    if geometry.pectoralis_support_shape == "curved_cap":
        x_span = max(0.018, 1.05 * geometry.radius)
        z_span = max(0.006, 1.0 * geometry.pectoralis_support_span_height)
        y_span = max(0.001, 1.15 * geometry.pectoralis_support_projection)

        x0 = -0.5 * x_span
        y_back = -geometry.thickness_chest_wall
        y_front = y_back + y_span
        z_low = max(0.0, z_center - 0.55 * z_span)
        z_high = min(geometry.posterior_support_height, z_center + 0.45 * z_span)

        p1 = build.addPoint(x0, y_back, z_low, settings.model.mesh.ls)
        p2 = build.addPoint(x0, y_front, z_low + 0.16 * z_span, settings.model.mesh.ls)
        p3 = build.addPoint(x0, y_front, z_center, settings.model.mesh.ls)
        p4 = build.addPoint(x0, y_front - 0.12 * y_span, z_high - 0.08 * z_span, settings.model.mesh.ls)
        p5 = build.addPoint(x0, y_back, z_high, settings.model.mesh.ls)

        l1 = build.addLine(p1, p2)
        l2 = build.addSpline([p2, p3, p4])
        l3 = build.addLine(p4, p5)
        l4 = build.addLine(p5, p1)
        loop = build.addCurveLoop([l1, l2, l3, l4])
        surface = build.addPlaneSurface([loop])
        extruded = build.extrude([(2, surface)], x_span, 0, 0)
        volume_tags = [tag for dim, tag in extruded if dim == dim3]
        if not volume_tags:
            raise RuntimeError("Failed to create curved-cap pectoralis volume")
        return volume_tags[0]

    if geometry.pectoralis_support_shape == "fascia_patch":
        x_span = max(0.028, 1.35 * geometry.radius)
        z_span = max(0.008, 1.2 * geometry.pectoralis_support_span_height)
        y_span = max(0.0007, 0.75 * geometry.pectoralis_support_projection)

        x0 = -0.5 * x_span
        y_back = -geometry.thickness_chest_wall
        y_front = y_back + y_span
        z_low = max(0.0, z_center - 0.52 * z_span)
        z_mid = z_center
        z_high = min(geometry.posterior_support_height, z_center + 0.48 * z_span)

        # Build a thin, broad posterior patch with a gently curved anterior face.
        p1 = build.addPoint(x0, y_back, z_low, settings.model.mesh.ls)
        p2 = build.addPoint(x0, y_front, z_low + 0.12 * z_span, settings.model.mesh.ls)
        p3 = build.addPoint(x0, y_front + 0.04 * y_span, z_mid, settings.model.mesh.ls)
        p4 = build.addPoint(x0, y_front, z_high - 0.10 * z_span, settings.model.mesh.ls)
        p5 = build.addPoint(x0, y_back, z_high, settings.model.mesh.ls)

        l1 = build.addLine(p1, p2)
        l2 = build.addSpline([p2, p3, p4])
        l3 = build.addLine(p4, p5)
        l4 = build.addLine(p5, p1)
        loop = build.addCurveLoop([l1, l2, l3, l4])
        surface = build.addPlaneSurface([loop])
        extruded = build.extrude([(2, surface)], x_span, 0, 0)
        volume_tags = [tag for dim, tag in extruded if dim == dim3]
        if not volume_tags:
            raise RuntimeError("Failed to create fascia-patch pectoralis volume")
        return volume_tags[0]

    x0 = -0.5 * x_span
    y0 = -geometry.thickness_chest_wall
    z0 = max(0.0, z_center - 0.5 * z_span)
    return build.addBox(x0, y0, z0, x_span, y_span, z_span)


def _rebuild_posterior_contour(build, settings, top_tag, bottom_tag, tag: int = 3):
    """
    Rebuild the visible posterior contour after gmsh fragment/remove steps.

    This is the curve that actually matters for side-view inspection in the
    stage-2 preview cases. If we recreate it as a straight line, any earlier
    posterior curvature gets visually lost.
    """
    geometry = settings.model.geometry

    if geometry.posterior_curve_depth <= 0.0:
        return build.addLine(top_tag, bottom_tag, tag)

    control_tag = build.addPoint(
        0,
        -geometry.thickness_chest_wall - geometry.posterior_curve_depth,
        0.5 * geometry.outer_pole_height,
        settings.model.mesh.ls,
    )
    return build.addSpline([top_tag, control_tag, bottom_tag], tag)


def generate_mesh(settings: Settings()):
    """
    In this function, the mesh is generated from settings extracted from the Settings class, in particular the mesh
    and geometry classes. These settings are explained in detail in model_settings.py under the MeshSettings and GeometrySettings
    classes.
    """

    mesh_parts = MeshParts()

    gmsh.initialize()
    gmsh.model.add("breast")

    gmsh.option.setNumber("Mesh.SaveAll", 1)
    gmsh.option.setNumber("General.Verbosity", 0)

    dim0, dim1, dim2, dim3 = 0, 1, 2, 3

    build = gmsh.model.occ
    mesh = gmsh.model.mesh

    #############################
    # Construct breast quadrant #
    #############################

    p1 = build.addPoint(0, 0, 0, settings.model.mesh.ls, 1)

    p2 = build.addPoint(0, settings.model.geometry.outer_tip_position, 0, settings.model.mesh.ls, 2)
    p3 = build.addPoint(
        0,
        settings.model.geometry.outer_pole_projection,
        settings.model.geometry.outer_pole_height,
        settings.model.mesh.ls,
        3,
    )

    l1 = _build_lower_profile_curve(build, settings, p1, p2)
    l2 = _build_outer_profile_curve(build, settings, p1, p2, p3)
    l3 = build.addLine(p3, p1, 3)

    loop1 = build.addCurveLoop([l1, l2, l3], 1)
    s1 = build.addPlaneSurface([loop1], 1)

    # Read asymmetry settings (only affects glandular ellipse)
    asym = settings.model.geometry.asymmetry

    scale_y = 1.0
    scale_z = 1.0

    if asym.enabled:
        scale_y = asym.scale_y
        scale_z = asym.scale_z

    p4 = build.addPoint(
        0,
        -settings.model.geometry.left_position_ellipse * scale_y,
        0,
        settings.model.mesh.ls,
        4
    )
    
    p5 = build.addPoint(
        0,
        settings.model.geometry.nipple_anchor_position * scale_y,
        0,
        settings.model.mesh.ls,
        5
    )

    p6 = build.addPoint(
        0,
        ((settings.model.geometry.nipple_anchor_position
        - settings.model.geometry.left_position_ellipse) / 2) * scale_y,
        -settings.model.geometry.position_center_ellipse * scale_z,
        settings.model.mesh.ls,
        6
    )

    l4 = build.addEllipseArc(p4, p6, p5, p5, 4)
    l5 = build.addLine(p4, p5, 5)

    loop2 = build.addCurveLoop([l4, l5], 2)
    s2 = build.addPlaneSurface([loop2], 2)

    p7 = build.addPoint(
        0,
        -settings.model.geometry.thickness_chest_wall,
        settings.model.geometry.posterior_support_height,
        settings.model.mesh.ls,
        7,
    )
    p8 = build.addPoint(0, -settings.model.geometry.thickness_chest_wall, 0, settings.model.mesh.ls, 8)

    l6 = build.addLine(p3, p7, 6)
    l7 = _build_posterior_support_curve(build, settings, p7, p8)
    l8 = build.addLine(p8, p1, 8)

    loop3 = build.addCurveLoop(([l8, l3, l6, l7]))
    s3 = build.addPlaneSurface([loop3])

    build.fragment([(dim2, s1), (dim2, s2)], [(dim2, s3)])
    build.synchronize()

    all_points = build.getEntities(dim0)
    all_lines = build.getEntities(dim1)
    all_surfaces = build.getEntities(dim2)
    point_coords = {idx: tuple(gmsh.model.getValue(dim0, idx, [])) for _, idx in all_points}

    for i in range(len(all_points)):
        idx = all_points[i][1]
        globals()['p%s' % idx] = idx

    for i in range(len(all_lines)):
        idx = all_lines[i][1]
        globals()['l%s' % idx] = idx

    build.remove(all_surfaces)

    lines_to_remove = _existing_entities("l", [3, 4, 5, 7, 8, 9, 11, 12, 14], dim1)
    points_to_remove = _existing_entities("p", [6, 10, 12, 14], dim0)
    if lines_to_remove:
        build.remove(lines_to_remove)
    if points_to_remove:
        build.remove(points_to_remove)

    reconnect = _resolve_rebuild_lines(build, settings.model.geometry.thickness_chest_wall)

    if not reconnect.get("anterior_already_connected", False):
        l3 = build.addLine(reconnect["anterior_lower"], reconnect["anterior_upper"], 3)
    l4 = build.addLine(reconnect["posterior_lower"], reconnect["posterior_upper"], 4)

    ###############################
    # 3D revolve
    ###############################

    all_current_lines = build.getEntities(dim1)
    build.revolve(all_current_lines, 0, 0, 0, 0, 1, 0, 2 * math.pi)

    tissues = mesh_parts.tissue_parts

    if settings.model.geometry.profile_asymmetry_enabled:
        # The stage-4 profile-asymmetry spline changes the revolve surface
        # ordering slightly. These loop selections were probed explicitly so the
        # nested gland/adipose volumes remain non-zero and meshable.
        surfloop_gland = build.addSurfaceLoop([1, 2, 3])
        surfloop_fat = build.addSurfaceLoop([1, 2, 3, 4, 6])
    else:
        surfloop_gland = build.addSurfaceLoop([1, 2, 5])
        surfloop_fat = build.addSurfaceLoop([1, 2, 3, 4, 6])

    gland_volume_tag = build.addVolume([surfloop_gland])
    adipose_volume_tag = build.addVolume([surfloop_fat])
    pectoralis_volume_tag = _add_pectoralis_volume(build, settings, dim3)

    if pectoralis_volume_tag is not None:
        _, volume_map = build.fragment(
            [(dim3, gland_volume_tag)],
            [(dim3, adipose_volume_tag), (dim3, pectoralis_volume_tag)],
        )
    else:
        _, volume_map = build.fragment([(dim3, gland_volume_tag)], [(dim3, adipose_volume_tag)])
    build.remove(build.getEntities(dim2))
    build.remove(build.getEntities(dim1))
    build.remove(build.getEntities(dim0))

    build.synchronize()
    glandular_tags = [tag for dim, tag in volume_map[0] if dim == dim3]
    adipose_candidates = [tag for dim, tag in volume_map[1] if dim == dim3]
    pectoralis_tags = []
    if pectoralis_volume_tag is not None and len(volume_map) > 2:
        pectoralis_tags = [tag for dim, tag in volume_map[2] if dim == dim3]
    adipose_tags = [tag for tag in adipose_candidates if tag not in glandular_tags and tag not in pectoralis_tags]

    if not glandular_tags:
        raise RuntimeError("Failed to resolve glandular volume tags after fragment")
    if not adipose_tags:
        raise RuntimeError("Failed to resolve adipose volume tags after fragment")
    if pectoralis_volume_tag is not None and not pectoralis_tags:
        raise RuntimeError("Failed to resolve pectoralis volume tags after fragment")

    skin_tags, chest_tags = _classify_external_surfaces()
    if not skin_tags:
        raise RuntimeError("Failed to resolve external skin surfaces after fragment")
    if not chest_tags:
        raise RuntimeError("Failed to resolve external chest surfaces after fragment")

    tissues.skin.tags = skin_tags
    tissues.chest.tags = chest_tags if len(chest_tags) > 1 else chest_tags[0]
    tissues.glandular.tags = glandular_tags if len(glandular_tags) > 1 else glandular_tags[0]
    tissues.adipose.tags = adipose_tags if len(adipose_tags) > 1 else adipose_tags[0]
    tissues.pectoralis.tags = (
        pectoralis_tags if len(pectoralis_tags) > 1 else (pectoralis_tags[0] if pectoralis_tags else [])
    )

    lobules = settings.material.glandular.hetero.build_lobules()

    if settings.model.mesh.debug_view and lobules:
        visualize_lobules_2d(lobules, settings, plane="xy", resolution=200)
        visualize_lobules_2d(lobules, settings, plane="yz", resolution=200)

    ####################
    # MESH GENERATION
    ####################

    curve_list = build.getEntities(dim1)
    for curve in curve_list:
        length_curve = build.getMass(dim1, curve[1])
        mesh.setTransfiniteCurve(curve[1], int(settings.model.mesh.density * length_curve))

    mesh.generate(dim3)

    mesh.setOrder(settings.model.mesh.order)

    if settings.model.mesh.optimize:
        if settings.model.mesh.order == 1:
            mesh.optimize()
        else:
            mesh.optimize("HighOrder")

    #########################################
    # MESH QUALITY CHECK
    #########################################

    try:
        elem_types, elem_tags, elem_nodes = mesh.getElements(dim3)

        qualities = []
        for etype, tags in zip(elem_types, elem_tags):
            q = gmsh.model.mesh.getElementQualities(tags, "minSJ")  # scaled jacobian
            qualities.extend(q)

        qualities = np.array(qualities)

        if len(qualities) > 0:
            logger.debug("Mesh quality check:")
            logger.debug(f"  Elements checked: {len(qualities)}")
            logger.debug(f"  Min quality: {qualities.min():.4f}")
            logger.debug(f"  Max quality: {qualities.max():.4f}")
            logger.debug(f"  Mean quality: {qualities.mean():.4f}")

            bad = np.sum(qualities < 0.1)
            logger.debug(f"  Poor quality elements (<0.1): {bad}")

            if bad > 0:
                logger.warning("Mesh contains low-quality elements (possible source-case instability)")
        else:
            logger.warning("Mesh quality check returned no elements")

    except Exception as e:
        logger.warning(f"Mesh quality check failed: {e}")

    if settings.model.mesh.debug_stop_after_mesh:
        logger.info("Stopping after mesh generation because debug_stop_after_mesh=true")
        if settings.model.mesh.debug_view:
            gmsh.fltk.run()
        gmsh.finalize()
        return mesh_parts

    #########################################
    # NODE / ELEMENT EXTRACTION
    #########################################

    for name in tissues.model_fields:
        if getattr(tissues, name).dim == 2:
            getattr(tissues, name).type = settings.model.mesh.elem_type_surface
        else:
            getattr(tissues, name).type = settings.model.mesh.elem_type_volume

        tags = getattr(tissues, name).tags

        if type(tags) == list:
            elements = []
            nodes = []
            last_valid_tag = None
            for tag in tags:
                tag_elem_types, tag_elem_tags, tag_elem_nodes = mesh.getElements(getattr(tissues, name).dim, tag)
                if len(tag_elem_types) == 0:
                    continue
                elements.append(tag_elem_tags[0])
                nodes.append(tag_elem_nodes[0])
                last_valid_tag = tag

            if not elements:
                getattr(tissues, name).elements = np.array([], dtype=int)
                getattr(tissues, name).nodes = np.empty((0, 0), dtype=int)
                continue

            elements = [int(item) for sublist in elements for item in sublist]
            nodes = np.array([int(item) for sublist in nodes for item in sublist])

            element_type = mesh.getElements(getattr(tissues, name).dim, last_valid_tag)[0][0]
            num_nodes = int(mesh.getElementProperties(element_type)[3])

            getattr(tissues, name).elements = elements
            getattr(tissues, name).nodes = nodes.reshape(-1, num_nodes)

        else:
            element_type, elements, nodes = mesh.getElements(
                getattr(tissues, name).dim,
                getattr(tissues, name).tags
            )
            if len(element_type) == 0:
                getattr(tissues, name).elements = np.array([], dtype=int)
                getattr(tissues, name).nodes = np.empty((0, 0), dtype=int)
                continue
            num_nodes = mesh.getElementProperties(element_type[0])[3]

            getattr(tissues, name).elements = elements[0]
            getattr(tissues, name).nodes = nodes[0].reshape(-1, num_nodes)

    #########################################
    # OUTPUT NODES
    #########################################

    node_tags, node_coords = gmsh.model.mesh.getNodes(returnParametricCoord=False)[0:2]
    node_coords = np.reshape(node_coords, (-1, 3))

    sorted_ids = node_tags.argsort()
    mesh_parts.nodes.tags = node_tags[sorted_ids]
    mesh_parts.nodes.coords = node_coords[sorted_ids]

    # Run the GUI to visualize the mesh (optional, can be commented out if not needed)
    if settings.model.mesh.debug_view:
        gmsh.fltk.run()
    
    gmsh.finalize()

    return mesh_parts

