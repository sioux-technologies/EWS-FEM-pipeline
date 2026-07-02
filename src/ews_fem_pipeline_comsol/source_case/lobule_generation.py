"""Deterministic glandular lobule layout generators.

The COMSOL pipeline uses these functions to create fan-shaped or Chen-inspired
lobule templates before converting them into COMSOL ellipsoid/duct primitives.
"""

import numpy as np


def _unit_vector(vec):
    norm = np.linalg.norm(vec)
    if norm < 1e-12:
        return np.array([0.0, -1.0, 0.0], dtype=float)
    return vec / norm


def _clamp_point_before_nipple(point, nipple, clearance):
    """
    Keep a template point posterior to the nipple by enforcing a minimum
    Euclidean clearance from the nipple center.
    """
    point = np.array(point, dtype=float)
    nipple = np.array(nipple, dtype=float)
    vec = point - nipple
    dist = np.linalg.norm(vec)
    if dist < 1e-12:
        point = nipple + np.array([0.0, -abs(clearance), 0.0], dtype=float)
    elif dist < clearance:
        point = nipple + vec / dist * clearance

    # Also enforce an anterior stop plane so no duct point can poke through
    # the nipple/areola region in the y-direction even if xz offset is large.
    point[1] = min(point[1], nipple[1] - abs(clearance))
    return point


def _transverse_chestwall_surface_y(x, radius, depth, center_x_offset=0.0):
    """
    Posterior breast/chestwall interface used by the transverse Stage 2
    curvature in the COMSOL builder.

    The transverse support is a cylinder with its axis in z, so the interface
    varies primarily over breast width x. The surface is 0 at the lateral edge
    and reaches `depth` near the centerline.
    """
    radius = max(float(radius), 1e-9)
    depth = max(float(depth), 1e-9)
    curve_radius = (radius * radius + depth * depth) / (2.0 * depth)
    curve_center_y = -(curve_radius - depth)
    x_clamped = min(abs(float(x) - float(center_x_offset)), radius)
    return max(0.0, curve_center_y + np.sqrt(max(curve_radius * curve_radius - x_clamped * x_clamped, 0.0)))


def _append_droplet_chain(
    lobules,
    base_center,
    nipple,
    base_width,
    amp_c1,
    amp_c2,
    amp_rho,
    droplet_length,
    droplet_components,
    lobe_id=None,
    ring_name=None,
):
    """
    Approximate a teardrop lobule by chaining Gaussian components from bulb to duct.
    """
    base_center = np.array(base_center, dtype=float)
    nipple = np.array(nipple, dtype=float)
    toward_nipple = _unit_vector(nipple - base_center)

    n_comp = max(1, int(droplet_components))
    for idx in range(n_comp):
        t = 0.0 if n_comp == 1 else idx / (n_comp - 1)
        center = base_center + toward_nipple * (t * droplet_length)
        width_scale = 1.0 - 0.45 * t
        amp_scale = 1.0 - 0.35 * t

        lobules.append(
            {
                "center": center.tolist(),
                "width": base_width * width_scale,
                "width_x": base_width * 0.75 * width_scale,
                "width_y": base_width * 1.35 * width_scale,
                "width_z": base_width * (0.95 + 0.25 * abs(toward_nipple[2])) * width_scale,
                "amp_c1": amp_c1 * amp_scale,
                "amp_c2": amp_c2 * amp_scale,
                "amp_rho": amp_rho * amp_scale,
                "lobe_id": lobe_id,
                "ring_name": ring_name,
                "component_index": idx,
                "component_count": n_comp,
                "component_role": "bulb" if idx == 0 else "duct",
            }
        )


def _generate_fan_lobules(
    n_lobes,
    n_per_lobe,
    nipple,
    lobe_length,
    spread_angle,
    width,
    amp_c1,
    amp_c2,
    amp_rho,
    seed,
):
    """
    Deterministic fan-shaped lobule layout in yz-plane.
    """
    rng = np.random.default_rng(seed)
    lobules = []
    nipple = np.array(nipple, dtype=float)
    angles = np.linspace(-spread_angle, spread_angle, n_lobes)

    for theta in angles:
        direction = np.array([0.0, np.cos(theta), np.sin(theta)])
        direction = _unit_vector(direction)

        for index in range(n_per_lobe):
            t = (index + 1) / (n_per_lobe + 1)
            radial_decay = 1.0 - 0.35 * t
            base_pos = nipple + direction * lobe_length * t

            jitter = rng.normal(0, width * 0.25, size=3)
            jitter -= direction * np.dot(jitter, direction)
            pos = base_pos + jitter * radial_decay

            lobules.append(
                {
                    "center": pos.tolist(),
                    "width": width * radial_decay,
                    "width_x": width * 0.80 * radial_decay,
                    "width_y": width * 1.10 * radial_decay,
                    "width_z": width * (1.0 + 0.4 * abs(direction[2])) * radial_decay,
                    "amp_c1": amp_c1,
                    "amp_c2": amp_c2,
                    "amp_rho": amp_rho,
                }
            )

    return lobules


def _generate_chen_double_ring_lobules(
    nipple,
    width,
    amp_c1,
    amp_c2,
    amp_rho,
    seed,
    inner_ring_count,
    outer_ring_count,
    inner_ring_radius,
    outer_ring_radius,
    inner_depth,
    outer_depth,
    droplet_length,
    droplet_components,
):
    """
    Chen-inspired lobe layout:
    - 18 lobe submodels in a double ring around the nipple
    - each lobe approximated as a teardrop chain toward the nipple
    """
    rng = np.random.default_rng(seed)
    nipple = np.array(nipple, dtype=float)
    lobules = []

    lobe_counter = 0

    def add_ring(count, ring_radius, depth, width_scale, phase, ring_name):
        nonlocal lobe_counter
        if count <= 0:
            return
        angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False) + phase
        for phi in angles:
            lobe_counter += 1
            base_center = np.array(
                [
                    ring_radius * np.cos(phi),
                    nipple[1] - depth,
                    ring_radius * np.sin(phi),
                ],
                dtype=float,
            )
            base_center += rng.normal(0.0, width * 0.08, size=3)
            _append_droplet_chain(
                lobules=lobules,
                base_center=base_center,
                nipple=nipple,
                base_width=width * width_scale,
                amp_c1=amp_c1,
                amp_c2=amp_c2,
                amp_rho=amp_rho,
                droplet_length=droplet_length,
                droplet_components=droplet_components,
                lobe_id=lobe_counter,
                ring_name=ring_name,
            )

    add_ring(
        count=inner_ring_count,
        ring_radius=inner_ring_radius,
        depth=inner_depth,
        width_scale=1.05,
        phase=0.0,
        ring_name="inner",
    )
    add_ring(
        count=outer_ring_count,
        ring_radius=outer_ring_radius,
        depth=outer_depth,
        width_scale=0.95,
        phase=np.pi / max(1, outer_ring_count),
        ring_name="outer",
    )

    return lobules


def _generate_chen_duct_lobes(
    nipple,
    width,
    amp_c1,
    amp_c2,
    amp_rho,
    seed,
    inner_ring_count,
    outer_ring_count,
    inner_ring_radius,
    outer_ring_radius,
    inner_depth,
    outer_depth,
    droplet_length,
    hub_offset_y,
    nipple_clearance_mid,
    nipple_clearance_tip,
):
    """
    COMSOL-oriented Chen-like lobe layout:
    - 18 anatomical lobes (8 inner + 10 outer)
    - each lobe represented by two primitives:
      1) a posterior bulb/sac
      2) an anterior duct directed toward the nipple
    """
    rng = np.random.default_rng(seed)
    nipple = np.array(nipple, dtype=float)
    lobules = []
    lobe_counter = 0
    hub_center = nipple - np.array([0.0, hub_offset_y, 0.0], dtype=float)

    def add_ring(count, ring_radius, depth, width_scale, phase, ring_name):
        nonlocal lobe_counter
        if count <= 0:
            return
        angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False) + phase
        for phi in angles:
            lobe_counter += 1
            bulb_center = np.array(
                [
                    ring_radius * np.cos(phi),
                    nipple[1] - depth,
                    ring_radius * np.sin(phi),
                ],
                dtype=float,
            )
            bulb_center += rng.normal(0.0, width * 0.04, size=3)

            toward_hub = _unit_vector(hub_center - bulb_center)
            duct_center = bulb_center + toward_hub * (0.74 * droplet_length)
            duct_center = _clamp_point_before_nipple(duct_center, nipple, nipple_clearance_mid)

            bulb_width = width * width_scale
            duct_width = bulb_width * 0.38

            lobules.append(
                {
                    "center": bulb_center.tolist(),
                    "width": bulb_width,
                    "width_x": bulb_width * 0.95,
                    "width_y": bulb_width * 1.22,
                    "width_z": bulb_width * 0.95,
                    "amp_c1": amp_c1,
                    "amp_c2": amp_c2,
                    "amp_rho": amp_rho,
                    "lobe_id": lobe_counter,
                    "ring_name": ring_name,
                    "component_index": 0,
                    "component_count": 2,
                    "component_role": "bulb",
                }
            )
            lobules.append(
                {
                    "center": duct_center.tolist(),
                    "width": duct_width,
                    "width_x": duct_width * 0.70,
                    "width_y": max(droplet_length * 0.72, duct_width * 1.8),
                    "width_z": duct_width * 0.70,
                    "amp_c1": amp_c1 * 0.92,
                    "amp_c2": amp_c2 * 0.92,
                    "amp_rho": amp_rho * 0.92,
                    "lobe_id": lobe_counter,
                    "ring_name": ring_name,
                    "component_index": 1,
                    "component_count": 2,
                    "component_role": "duct",
                }
            )

    add_ring(
        count=inner_ring_count,
        ring_radius=inner_ring_radius,
        depth=inner_depth,
        width_scale=1.02,
        phase=0.0,
        ring_name="inner",
    )
    add_ring(
        count=outer_ring_count,
        ring_radius=outer_ring_radius,
        depth=outer_depth,
        width_scale=0.92,
        phase=np.pi / max(1, outer_ring_count),
        ring_name="outer",
    )

    return lobules


def _generate_chen_template_lobes(
    nipple,
    width,
    amp_c1,
    amp_c2,
    amp_rho,
    seed,
    inner_ring_count,
    outer_ring_count,
    inner_ring_radius,
    outer_ring_radius,
    inner_depth,
    outer_depth,
    droplet_length,
    hub_offset_y,
    nipple_clearance_mid,
    nipple_clearance_tip,
    chestwall_aware_lobules=False,
    chestwall_reference_radius_m=0.07,
    chestwall_curve_depth_m=0.0045,
    chestwall_curve_center_x_offset_m=0.0,
    chestwall_clearance_m=0.003,
    chestwall_posterior_margin_scale=2.85,
):
    """
    Generate 18 anatomical lobe templates for COMSOL placement.

    Each template describes one lobe with:
    - a posterior bulb center and radii
    - a sidecar offset to avoid perfect ellipsoid bulbs
    - a curved duct represented by a mid point and a distal tip that stops
      short of the nipple/areola region
    """
    rng = np.random.default_rng(seed)
    nipple = np.array(nipple, dtype=float)
    lobules = []
    lobe_counter = 0
    hub_center = nipple - np.array([0.0, hub_offset_y, 0.0], dtype=float)

    def add_ring(count, ring_radius, depth, width_scale, phase, ring_name):
        nonlocal lobe_counter
        if count <= 0:
            return
        angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False) + phase
        for phi in angles:
            lobe_counter += 1
            bulb_center = np.array(
                [
                    ring_radius * np.cos(phi),
                    nipple[1] - depth,
                    ring_radius * np.sin(phi),
                ],
                dtype=float,
            )
            jitter = rng.normal(0.0, width * 0.010, size=3)
            jitter[1] = 0.0
            bulb_center += jitter

            is_outer = ring_name == "outer"
            bulb_width = width * width_scale * (1.18 if is_outer else 1.16)
            chestwall_y = None
            chestwall_adjustment_y = 0.0
            if chestwall_aware_lobules:
                chestwall_y = _transverse_chestwall_surface_y(
                    bulb_center[0],
                    chestwall_reference_radius_m,
                    chestwall_curve_depth_m,
                    chestwall_curve_center_x_offset_m,
                )
                posterior_allowance = max(
                    chestwall_posterior_margin_scale * bulb_width,
                    bulb_width + chestwall_clearance_m,
                )
                target_center_y = chestwall_y + chestwall_clearance_m + posterior_allowance
                max_center_y = nipple[1] - max(nipple_clearance_mid + 0.006, 0.014)
                adjusted_center_y = min(max(bulb_center[1], target_center_y), max_center_y)
                chestwall_adjustment_y = adjusted_center_y - bulb_center[1]
                bulb_center[1] = adjusted_center_y

            toward_hub = _unit_vector(hub_center - bulb_center)
            tangent = np.array([-np.sin(phi), 0.0, np.cos(phi)], dtype=float)
            tangent = _unit_vector(tangent)
            radial = np.array([np.cos(phi), 0.0, np.sin(phi)], dtype=float)
            radial = _unit_vector(radial)

            curvature = 0.0012 if is_outer else 0.0007
            posterior_bias = 0.72 if is_outer else 0.64
            duct_mid = bulb_center + toward_hub * (posterior_bias * droplet_length)
            duct_mid += tangent * curvature
            duct_mid -= radial * ((0.02 if is_outer else 0.01) * width)
            duct_mid = _clamp_point_before_nipple(duct_mid, nipple, nipple_clearance_mid)

            target_tip = hub_center.copy()
            target_tip += tangent * ((0.0010 if is_outer else 0.0006) * np.sign(np.sin(phi + 1e-9)))
            target_tip += radial * (0.0005 if is_outer else 0.0003)
            duct_tip = _clamp_point_before_nipple(target_tip, nipple, nipple_clearance_tip)

            bulb_sidecar = bulb_center + radial * (0.82 * bulb_width) - tangent * (0.10 * bulb_width)
            bulb_sidecar[1] -= 0.18 * bulb_width

            lobules.append(
                {
                    "center": bulb_center.tolist(),
                    "width": bulb_width,
                    "width_x": bulb_width * (0.78 if is_outer else 0.82),
                    "width_y": bulb_width * (2.05 if is_outer else 1.92),
                    "width_z": bulb_width * (0.82 if is_outer else 0.86),
                    "amp_c1": amp_c1,
                    "amp_c2": amp_c2,
                    "amp_rho": amp_rho,
                    "lobe_id": lobe_counter,
                    "ring_name": ring_name,
                    "component_index": 0,
                    "component_count": 1,
                    "component_role": "bulb",
                    "template_kind": "duct_lobe",
                    "duct_mid": duct_mid.tolist(),
                    "duct_tip": duct_tip.tolist(),
                    "bulb_sidecar": bulb_sidecar.tolist(),
                    "chestwall_y": chestwall_y,
                    "chestwall_clearance": chestwall_clearance_m if chestwall_aware_lobules else None,
                    "chestwall_adjustment_y": chestwall_adjustment_y if chestwall_aware_lobules else None,
                }
            )

    add_ring(
        count=inner_ring_count,
        ring_radius=inner_ring_radius,
        depth=inner_depth,
        width_scale=1.00,
        phase=0.0,
        ring_name="inner",
    )
    add_ring(
        count=outer_ring_count,
        ring_radius=outer_ring_radius,
        depth=outer_depth,
        width_scale=1.00,
        phase=0.0,
        ring_name="outer",
    )
    return lobules


def generate_lobules(
    n_lobes,
    n_per_lobe,
    nipple,
    lobe_length,
    spread_angle,
    width,
    amp_c1,
    amp_c2,
    amp_rho,
    generator_mode="fan",
    inner_ring_count=8,
    outer_ring_count=10,
    inner_ring_radius=0.005,
    outer_ring_radius=0.009,
    inner_depth=0.012,
    outer_depth=0.020,
    droplet_length=0.007,
    droplet_components=2,
    hub_offset_y=0.0125,
    nipple_clearance_mid=0.015,
    nipple_clearance_tip=0.011,
    chestwall_aware_lobules=False,
    chestwall_reference_radius_m=0.07,
    chestwall_curve_depth_m=0.0045,
    chestwall_curve_center_x_offset_m=0.0,
    chestwall_clearance_m=0.003,
    chestwall_posterior_margin_scale=2.85,
    seed=42,
):
    """
    Generate lobules using either the legacy fan model or a Chen-inspired double-ring model.
    """
    if generator_mode == "chen_2024_double_ring":
        return _generate_chen_double_ring_lobules(
            nipple=nipple,
            width=width,
            amp_c1=amp_c1,
            amp_c2=amp_c2,
            amp_rho=amp_rho,
            seed=seed,
            inner_ring_count=inner_ring_count,
            outer_ring_count=outer_ring_count,
            inner_ring_radius=inner_ring_radius,
            outer_ring_radius=outer_ring_radius,
            inner_depth=inner_depth,
            outer_depth=outer_depth,
            droplet_length=droplet_length,
            droplet_components=droplet_components,
        )

    if generator_mode == "chen_2024_duct_lobes":
        return _generate_chen_duct_lobes(
            nipple=nipple,
            width=width,
            amp_c1=amp_c1,
            amp_c2=amp_c2,
            amp_rho=amp_rho,
            seed=seed,
            inner_ring_count=inner_ring_count,
            outer_ring_count=outer_ring_count,
            inner_ring_radius=inner_ring_radius,
            outer_ring_radius=outer_ring_radius,
            inner_depth=inner_depth,
            outer_depth=outer_depth,
            droplet_length=droplet_length,
            hub_offset_y=hub_offset_y,
            nipple_clearance_mid=nipple_clearance_mid,
            nipple_clearance_tip=nipple_clearance_tip,
        )

    if generator_mode == "chen_2024_template_lobes":
        return _generate_chen_template_lobes(
            nipple=nipple,
            width=width,
            amp_c1=amp_c1,
            amp_c2=amp_c2,
            amp_rho=amp_rho,
            seed=seed,
            inner_ring_count=inner_ring_count,
            outer_ring_count=outer_ring_count,
            inner_ring_radius=inner_ring_radius,
            outer_ring_radius=outer_ring_radius,
            inner_depth=inner_depth,
            outer_depth=outer_depth,
            droplet_length=droplet_length,
            hub_offset_y=hub_offset_y,
            nipple_clearance_mid=nipple_clearance_mid,
            nipple_clearance_tip=nipple_clearance_tip,
            chestwall_aware_lobules=chestwall_aware_lobules,
            chestwall_reference_radius_m=chestwall_reference_radius_m,
            chestwall_curve_depth_m=chestwall_curve_depth_m,
            chestwall_curve_center_x_offset_m=chestwall_curve_center_x_offset_m,
            chestwall_clearance_m=chestwall_clearance_m,
            chestwall_posterior_margin_scale=chestwall_posterior_margin_scale,
        )

    return _generate_fan_lobules(
        n_lobes=n_lobes,
        n_per_lobe=n_per_lobe,
        nipple=nipple,
        lobe_length=lobe_length,
        spread_angle=spread_angle,
        width=width,
        amp_c1=amp_c1,
        amp_c2=amp_c2,
        amp_rho=amp_rho,
        seed=seed,
    )


def visualize_lobules_2d_old(lobules, settings, resolution=200):
    """
    Visualize the projected glandular field in the x-y plane.
    """
    import matplotlib.pyplot as plt

    radius = settings.model.geometry.radius
    nipple = settings.material.glandular.hetero.nipple

    x = np.linspace(-radius, radius, resolution)
    y = np.linspace(0.0, radius, resolution)
    grid_x, grid_y = np.meshgrid(x, y)
    field = np.zeros_like(grid_x)

    for lobule in lobules:
        center_x, center_y, _ = lobule.center
        sigma = lobule.width
        amplitude = lobule.amp_rho
        field += amplitude * np.exp(-((grid_x - center_x) ** 2 + (grid_y - center_y) ** 2) / (sigma ** 2))

    plt.figure(figsize=(6, 6))
    plt.imshow(field, extent=[x.min(), x.max(), y.min(), y.max()], origin="lower")
    plt.colorbar(label="Glandular density")

    theta = np.linspace(0, np.pi, 200)
    boundary_x = radius * np.cos(theta)
    boundary_y = radius * np.sin(theta)
    plt.plot(boundary_x, boundary_y, "w--", label="breast boundary")
    plt.scatter(nipple[0], nipple[1], c="red", s=80, label="nipple")

    for lobule in lobules:
        plt.scatter(lobule.center[0], lobule.center[1], c="black", s=10)

    plt.xlabel("x")
    plt.ylabel("y")
    plt.title("Glandular field")
    plt.legend()
    plt.tight_layout()
    plt.show()

def visualize_lobules_2d(lobules, settings, plane="xy", resolution=200):
    """
    Visualize projected glandular field in xy or yz plane.
    """
    import matplotlib.pyplot as plt

    radius = settings.model.geometry.radius
    nipple = settings.material.glandular.hetero.nipple

    if plane == "xy":
        a = np.linspace(-radius, radius, resolution)   # x
        b = np.linspace(0.0, radius, resolution)       # y
        label_a, label_b = "x", "y"

    elif plane == "yz":
        a = np.linspace(0.0, radius, resolution)       # y
        b = np.linspace(-radius, radius, resolution)   # z
        label_a, label_b = "y", "z"

    else:
        raise ValueError("plane must be 'xy' or 'yz'")

    grid_a, grid_b = np.meshgrid(a, b)
    field = np.zeros_like(grid_a)

    for lobule in lobules:
        cx, cy, cz = lobule.center
        sigma_x = lobule.width_x if hasattr(lobule, "width_x") and lobule.width_x is not None else lobule.width
        sigma_y = lobule.width_y if hasattr(lobule, "width_y") and lobule.width_y is not None else lobule.width
        sigma_z = lobule.width_z if hasattr(lobule, "width_z") and lobule.width_z is not None else lobule.width
        amplitude = lobule.amp_rho

        if plane == "xy":
            da = grid_a - cx
            db = grid_b - cy
            field += amplitude * np.exp(-(da**2 / (sigma_x**2) + db**2 / (sigma_y**2)))
        else:  # yz
            da = grid_a - cy
            db = grid_b - cz
            field += amplitude * np.exp(-(da**2 / (sigma_y**2) + db**2 / (sigma_z**2)))

    plt.figure(figsize=(6, 6))
    plt.imshow(field, extent=[a.min(), a.max(), b.min(), b.max()], origin="lower")
    plt.colorbar(label="Glandular density")

    # 🔵 Breast boundary (halve cirkel)
    theta = np.linspace(0, np.pi, 200)
    if plane == "xy":
        boundary_a = radius * np.cos(theta)
        boundary_b = radius * np.sin(theta)
    else:  # yz
        boundary_a = radius * np.sin(theta)   # y
        boundary_b = radius * np.cos(theta)   # z

    plt.plot(boundary_a, boundary_b, "w--", label="breast boundary")

    # 🔴 Nipple
    if plane == "xy":
        plt.scatter(nipple[0], nipple[1], c="red", s=80, label="nipple")
    else:
        plt.scatter(nipple[1], nipple[2], c="red", s=80, label="nipple")

    # ⚫ Lobules
    for lobule in lobules:
        if plane == "xy":
            plt.scatter(lobule.center[0], lobule.center[1], c="black", s=10)
        else:
            plt.scatter(lobule.center[1], lobule.center[2], c="black", s=10)

    # 🟫 Chest wall (alleen zinvol in yz)
    if plane == "yz":
        # aannemen: chest wall op y = 0
        plt.axvline(x=0.0, color="cyan", linestyle="--", label="chest wall")

    plt.xlabel(label_a)
    plt.ylabel(label_b)
    plt.title(f"Glandular field ({plane}-plane)")
    plt.legend()
    plt.tight_layout()
    plt.show()
