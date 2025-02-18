from pydantic import BaseModel, Field


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
    """

    radius: float = 0.07
    thickness_chest_wall: float = 0.002
    left_relative_position_ellipse: float = 0.4
    right_relative_position_ellipse: float = 0.05
    center_relative_position_ellipse: float = 0.3

    @property
    def left_position_ellipse(self):
        return self.left_relative_position_ellipse * self.radius

    @property
    def position_nipple(self):
        return self.right_relative_position_ellipse * self.radius

    @property
    def position_center_ellipse(self):
        return self.center_relative_position_ellipse * self.radius


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
    """

    ls: float = 0.005
    density: float = 260
    optimize: bool = True
    order: int = Field(2, ge=1, le=2)

    _surface_map = {1: ' tri3', 2: 'tri6'}
    _volume_map = {1: ' tet4', 2: 'tet10'}

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


class MeshParts(BaseModel):
    """
    Unites the nodes and the tissues parts for all tissues in a single class, for easier reference.
    """
    nodes: Nodes = Nodes()
    tissue_parts: TissueParts = TissueParts()

