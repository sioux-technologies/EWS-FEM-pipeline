"""Source-case geometry and mesh settings used before COMSOL Java generation.

These pydantic models describe the analytical breast profile, mesh generation
parameters, and named tissue parts exported by the source-case prepare step.
"""

from typing import Literal

from pydantic import BaseModel, Field


class AsymmetrySettings(BaseModel):
    """
    Controls simple geometric asymmetry scaling in Y and Z directions.
    """

    enabled: bool = False
    scale_y: float = 1.0
    scale_z: float = 1.0

class GeometrySettings(BaseModel):
    """
    ================
    INPUT PARAMETERS
    ================

    - radius: float [m > 0]                             Set the radius of the breast, which is modelled as a hemisphere.
                                                        ALL PARAMETERS (EXCEPT FOR thickness_disk) ARE SCALED w.r.t.
                                                        THE RADIUS!
    - thickness_chest_wall: float [m > 0]               Sets the thickness of the disk attached to the chest wall. The disk
                                                        is subjected to the boundary conditions of the parabolic jump.
    - left_relative_position_ellipse: float [m > 0]     Adds a point left of the chest where the glandular ellipse
                                                        starts. This point acts as a placeholder for the left side of
                                                        the ellipse and is removed later.
    - right_relative_position_ellipse: float [m > 0]    This parameter sets the position of the nipple, scaled with the
                                                        radius.
    - center_relative position_ellipse: float [m > 0]   Sets the center point of the ellipse. This parameter shifts the
                                                        glandular part down/up, which causes sharper/obtuse angles in
                                                        the nipple.
    - outer_profile_mode: str                           Keeps the legacy circular outer contour by default, or switches
                                                        to an elliptical contour when stage-1 outer geometry refactoring
                                                        is enabled explicitly.
    - anterior_projection_scale: float [m > 0]          Scales the anterior extent of the breast envelope in the
                                                        axisymmetric source profile.
    - superior_pole_scale: float [m > 0]                Scales the superior pole height of the breast envelope in the
                                                        axisymmetric source profile.
    - upper_pole_projection_ratio: float [m >= 0]      Projects the superior pole slightly anteriorly as a fraction of the
                                                        effective outer-front position. This helps move away from the
                                                        perfectly upright pole used by the earlier axisymmetric source
                                                        profile.
    - posterior_support_height_scale: float [m > 0]    Scales the superior height of the posterior chest support. Values
                                                        slightly below 1.0 create a gentler posterior transition into the
                                                        chest wall.
    - posterior_curve_depth_ratio: float [m >= 0]      Adds a shallow posterior curvature to the chest-support wall as
                                                        a fraction of the breast radius. This is intended as a light
                                                        thorax-inspired refinement rather than a full explicit torso model.
    - pectoralis_support_projection_scale: float [> 0] Moves the posterior support interface slightly anteriorly in
                                                        the upper-middle region as a multiple of the chest-wall
                                                        thickness. This is meant as a pectoralis-lite support proxy,
                                                        not as a separate muscle domain.
    - pectoralis_support_shape: str                     Selects the simplified pectoralis support-domain geometry.
                                                        `slab` keeps a broad posterior support patch, while
                                                        `curved_cap` uses an elliptical cap-like volume that better
                                                        follows the literature direction of a curved pectoralis layer.
    - pectoralis_support_center_ratio: float [0..1]    Sets the center height of the pectoralis-lite support bulge as
                                                        a fraction of the posterior support height.
    - pectoralis_support_span_ratio: float [0..1]      Sets the vertical span of the pectoralis-lite support bulge as
                                                        a fraction of the posterior support height.
    - asymmetry: AsymmetrySettings                      Controls simple geometric asymmetry scaling in Y and Z directions.                                                
    - profile_asymmetry_enabled: bool                  Enables a first stage-4 side-profile asymmetry refinement while
                                                       keeping the model revolved/axisymmetric in 3D.
    - inferior_fullness_ratio: float [m >= 0]         Adds controlled anterior fullness to the lower pole as a fraction
                                                       of the front radius. This moves the profile away from the overly
                                                       symmetric D-shape.
    - superior_flattening_ratio: float [m >= 0]       Pulls the upper contour slightly posteriorly, creating a gentler
                                                       superior pole instead of a near-perfect circular arc.
    - nipple_projection_ratio: float [m >= 0]         Adds a small explicit anterior tip beyond the breast body-front
                                                       position. This stabilizes the nipple/front silhouette so profile
                                                       refinements do not visually cut off the anterior tip.
    - nipple_transition_height_ratio: float [m >= 0]  Sets the height over which the outer contour transitions from the
                                                       nipple tip back into the main breast envelope.
    """

    radius: float = 0.07
    thickness_chest_wall: float = 0.002
    left_relative_position_ellipse: float = 0.4
    right_relative_position_ellipse: float = 0.05
    center_relative_position_ellipse: float = 0.3
    outer_profile_mode: Literal["circular", "elliptic"] = "circular"
    anterior_projection_scale: float = 1.0
    superior_pole_scale: float = 1.0
    upper_pole_projection_ratio: float = 0.0
    posterior_support_height_scale: float = 1.0
    posterior_curve_depth_ratio: float = 0.0
    pectoralis_support_projection_scale: float = 0.0
    pectoralis_support_shape: Literal["slab", "curved_cap", "fascia_patch"] = "slab"
    pectoralis_support_center_ratio: float = 0.62
    pectoralis_support_span_ratio: float = 0.32
    profile_asymmetry_enabled: bool = False
    inferior_fullness_ratio: float = 0.0
    superior_flattening_ratio: float = 0.0
    nipple_projection_ratio: float = 0.0
    nipple_transition_height_ratio: float = 0.06

    asymmetry: AsymmetrySettings = AsymmetrySettings()

    @property
    def left_position_ellipse(self):
        return self.left_relative_position_ellipse * self.radius

    @property
    def position_nipple(self):
        return self.right_relative_position_ellipse * self.radius

    @property
    def position_center_ellipse(self):
        return self.center_relative_position_ellipse * self.radius

    @property
    def outer_front_position(self):
        return self.radius * self.anterior_projection_scale

    @property
    def outer_pole_height(self):
        return self.radius * self.superior_pole_scale

    @property
    def outer_pole_projection(self):
        return self.outer_front_position * self.upper_pole_projection_ratio

    @property
    def posterior_support_height(self):
        return self.outer_pole_height * self.posterior_support_height_scale

    @property
    def posterior_curve_depth(self):
        return self.radius * self.posterior_curve_depth_ratio

    @property
    def pectoralis_support_projection(self):
        return self.thickness_chest_wall * self.pectoralis_support_projection_scale

    @property
    def pectoralis_support_center_height(self):
        return self.posterior_support_height * self.pectoralis_support_center_ratio

    @property
    def pectoralis_support_span_height(self):
        return self.posterior_support_height * self.pectoralis_support_span_ratio

    @property
    def nipple_anchor_position(self):
        return self.outer_front_position + self.position_nipple

    @property
    def outer_tip_position(self):
        return self.outer_front_position + self.radius * self.nipple_projection_ratio

    @property
    def nipple_transition_height(self):
        return self.outer_pole_height * self.nipple_transition_height_ratio


class MeshSettings(BaseModel):
    """
    ================
    INPUT PARAMETERS
    ================

    - ls: float [> 0]       Sets the default mesh size, but will later be overwritten by the "density". Is required to
                            set the gmsh mesh size.
    - density: float [>0]   Sets the true mesh size. The number is a measure for the number of nodes per unit of length.
                            A greater value implies a denser mesh. Cannot be set smaller than 90.
    - optimize: bool        Optimizes the mesh of the model using the default gmsh tetrahedral mesh optimizer, or the
                            "HighOrder" optimizer for high order meshes (see input parameter "order").
    - order: int [1 or 2]   Sets the order of the elements. Can only be 1 or 2. Order 1 implies tri3 en tet4 elements,
                            while order 2 implies tri6 and tet10 elements.
    - debug_view: bool      If True, runs the gmsh GUI to visualize the mesh after generation. Can be helpful for debugging                        
    """

    ls: float = 0.005
    density: float = 260
    optimize: bool = True
    debug_view: bool = False
    debug_stop_after_mesh: bool = False
    order: int = Field(2, ge=1, le=2)

    _surface_map = {1: "tri3", 2: "tri6"}
    _volume_map = {1: "tet4", 2: "tet10"}

    @property
    def elem_type_surface(self):
        return self._surface_map[self.order]

    @property
    def elem_type_volume(self):
        return self._volume_map[self.order]


# Class containing all objects for single tissue component in breast
class MeshObject(BaseModel):
    """
    Contains the fields of the mesh objects: [chest, skin, adipose, glandular].
    """

    type: str = None
    elements: list = None
    nodes: list = None
    name: str = None
    tags: list = None
    dim: int = None


class Nodes(BaseModel):
    """
    Contains the fields of all the nodes.
    """
    tags: list = None
    coords: list = None


# Class containing all tissue components in breast
class TissueParts(BaseModel):
    """
    Assigns the name and dimensionality to the mesh objects from MeshObject class
    """
    skin: MeshObject = MeshObject(name="skin_part", dim=2)
    chest: MeshObject = MeshObject(name="chest_part", dim=2)
    adipose: MeshObject = MeshObject(name="adipose_part", dim=3)
    glandular: MeshObject = MeshObject(name="glandular_part", dim=3)
    pectoralis: MeshObject = MeshObject(name="pectoralis_part", dim=3)


class MeshParts(BaseModel):
    """
    Unites the nodes and the tissues parts for all tissues in a single class, for easier reference.
    """
    nodes: Nodes = Nodes()
    tissue_parts: TissueParts = TissueParts()
