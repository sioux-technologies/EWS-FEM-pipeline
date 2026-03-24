from pydantic import BaseModel, Field


class GeometrySettings(BaseModel):
    """
    ================
    INPUT PARAMETERS
    ================

    - radius_breast: float [m > 0]                      Set the radius of the breast, which is modelled as a hemisphere.
                                                        ALL PARAMETERS (EXCEPT FOR thickness_disk) ARE SCALED w.r.t.
                                                        THE RADIUS!
    - asym_p1: float                                    Shape of the breast base is defined by variable radius
    - asym_p2: float                                    r = radius_breast(1+p1*cos(theta)+p2*cos(2*theta)
    - asym_p3: float                                                            + p3*cos(3*theta))
    - radius_nipple: [m > 0.0035]                       Set the radius of the nipple and duct , modeled as a cylinder
                                                        extending from the main glandular tissue of the breast.
    - thickness_chest_wall: float [m > 0]               Sets the thickness of the disk attached to the chest wall. The disk
                                                        is subjected to the boundary conditions of the parabolic jump.
    - scaling_factor_glandular: float [0 < f < 1]       Set the ratio of radius of breast : radius of glandular tissue
                                                        in all three dimensions.
    - angle_nipple: float [deg < 90]                    Sets the angle of the nipple with respect to the body front. The
                                                        radius of the chest curvature is scaled accordingly.
    """

    radius_breast: float = 0.07
    thickness_chest_wall: float = 0.002
    radius_nipple: float = 0.005
    scaling_factor_glandular: float = 0.8
    angle_nipple: float = 30
    asym_p1: float = 0.12
    asym_p2: float = 0.02
    asym_p3: float = 0.03



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

    _surface_map = {1: 'tri3', 2: 'tri6'}
    _volume_map = {1: 'tet4', 2: 'tet10'}

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

