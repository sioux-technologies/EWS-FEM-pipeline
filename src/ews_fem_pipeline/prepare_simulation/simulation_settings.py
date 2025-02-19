import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Annotated

import numpy as np
from pydantic import BaseModel, field_validator
from pydantic_core.core_schema import ValidationInfo

from ews_fem_pipeline.prepare_simulation.model_settings import GeometrySettings, MeshSettings


@dataclass
class FEBField:
    """
    The lowest level field, which contains all tags that build up the .feb file.
    """
    tag: str
    val: str | float | int | None = None
    id: str | None = None
    name: str | None = None
    type: str | None = None
    lc: str | None = None
    mat: str | None = None
    elem_set: str | None = None
    node_set: str | None = None

    @property
    def xml_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items()
                if k not in ["tag", "val"] and v is not None}

    def to_xml(self, parent):
        kwargs = self.xml_dict

        elem = ET.SubElement(parent, self.tag, **kwargs)
        if self.val is not None:
            elem.text = f"{self.val}"

        return elem


class FEBElement(BaseModel):
    """
    Class containing all elements that make up the .feb file.
    """
    module: FEBField = FEBField(tag="Module", type="solid")
    globals: FEBField = FEBField(tag="Globals")
    constants: FEBField = FEBField(tag="Constants")
    material: FEBField = FEBField(tag="Material")
    skin: FEBField = FEBField(tag="material", id="1", name="skin", type="Mooney-Rivlin")
    adipose: FEBField = FEBField(tag="material", id="2", name="adipose", type="Mooney-Rivlin")
    glandular: FEBField = FEBField(tag="material", id="3", name="glandular", type="Mooney-Rivlin")
    mesh: FEBField = FEBField(tag="Mesh")
    mass_damping: FEBField = FEBField(tag="PartList", val="skin_part,glandular_part,adipose_part", name="Mass_damping")
    gravitational_acceleration: FEBField = FEBField(tag="PartList", val="skin_part,glandular_part,adipose_part",
                                                    name="gravitational_acceleration")
    mesh_domains: FEBField = FEBField(tag="MeshDomains")
    shell_domain: FEBField = FEBField(tag="ShellDomain", name="skin_part", mat="skin")
    shell_thickness: FEBField = FEBField(tag="shell_thickness", val="0.0001")
    solid_domain_glandular: FEBField = FEBField(tag="SolidDomain", name="glandular_part", mat="glandular")
    solid_domain_adipose: FEBField = FEBField(tag="SolidDomain", name="adipose_part", mat="adipose")
    loads: FEBField = FEBField(tag="Loads")
    body_load1: FEBField = FEBField(tag="body_load", elem_set="@part_list:gravitational_acceleration",
                                    type="body force")
    body_load2: FEBField = FEBField(tag="body_load", elem_set="@part_list:Mass_damping", type="mass damping")
    force: FEBField = FEBField(tag="force", lc="1", val="0,0,9.81")
    step: FEBField = FEBField(tag="Step")
    step1: FEBField = FEBField(tag="step", id="1", name="Step1")
    step2: FEBField = FEBField(tag="step", id="2", name="Step2")
    control: FEBField = FEBField(tag="Control")
    time_stepper: FEBField = FEBField(tag="time_stepper", type="default")
    solver: FEBField = FEBField(tag="solver", type="solid")
    qn_method: FEBField = FEBField(tag="qn_method", type="BFGS")
    boundary: FEBField = FEBField(tag="Boundary")
    boundary_zero_displacement: FEBField = FEBField(tag="bc", name="chest", node_set="@surface:chest_part",
                                                    type="zero displacement")
    boundary_parabolic_trajectory: FEBField = FEBField(tag="bc", name="parabolic_trajectory",
                                                       node_set="@surface:chest_part", type="prescribed displacement")
    boundary_only_z_displacement: FEBField = FEBField(tag="bc", name="only_z_displacement",
                                                      node_set="@surface:chest_part", type="zero displacement")
    load_data: FEBField = FEBField(tag="LoadData")
    output: FEBField = FEBField(tag="Output")


class ExtendedBaseModel(BaseModel):
    """
    Class to process and print multiple FEBFields to the .feb file.
    """

    @field_validator("*", mode="before")
    @classmethod
    def validate(cls, data, info: ValidationInfo):
        field_info = cls.model_fields[info.field_name]

        if isinstance(data, dict) and isinstance(field_info.default, BaseModel):
            # If it is a dict, we can check and fill the default values
            data = {**field_info.default.model_dump(), **data}

        return data

    def to_xml(self, parent):
        for name, info in self.model_fields.items():
            field_value = getattr(self, name)

            if hasattr(field_value, "to_xml"):
                # In this case, the item itself can create an xml element
                field_value.to_xml(parent)

            else:
                # This should be a bit neater: it could be possible that more
                # than 1 metadata field exists... especially if you want to
                # add validation
                assert len(info.metadata) == 1
                md = info.metadata[0]
                assert isinstance(md, FEBField)
                ET.SubElement(parent, md.tag, **md.xml_dict).text = f"{field_value}"


class Constants(ExtendedBaseModel):
    """
    Class containing the basic physical constants
    """
    temperature: FEBField = FEBField(tag="T", val="0")
    pressure: FEBField = FEBField(tag="P", val="0")
    gas_constant: FEBField = FEBField(tag="R", val="8.31446")
    faraday_constant: FEBField = FEBField(tag="Fc", val="96485.3")


class TumorProperties(BaseModel):
    """
    ======================
    INPUT PARAMETERS TUMOR
    ======================
    For the tumor, we assume the Mooney-Rivlin material type, which takes two arguments: coef1, the coefficient of the
    first invariant term; coef2 coefficient of second invariant term.

    - tumorous: bool                    If TRUE, places a spherical tumor with the below listed parameters. If FALSE, no
                                        tumor is placed and the code ignores these parameters.
    - density: float [kg/m^3 > 0]       Sets the mass density of the tumor.
    - radius: float [m > 0]             Sets the absolute radius [m] of the spherical tumor. NOTE: Does not scale with
                                        "radius" from GeometrySettings in model_settings.py.
    - position: list[float] [m > 0]     Sets the absolute position (x [m], y [m], z[m]) of the tumor in space. NOTE:
                                        Does not scale with "radius" from GeometrySettings in model_settings.py. Make
                                        sure the tumor is in fact INSIDE the breast.
    - coef1_adipose: float [Pa > 0]    Sets the tumor coef1 when inside the adipose part.
    - coef2_adipose: float [Pa > 0]    Sets the tumor coef2 when inside the adipose part.
    - coef1_glandular: float [Pa > 0]  Sets the tumor coef1 when inside the glandular part.
    - coef2_glandular: float [Pa > 0]  Sets the tumor coef2 when inside the glandular part.
    """

    tumorous: bool = True
    density: float = 1079
    radius: float = 0.005
    position: list[float] = [0.035, 0.040, 0]  # (x,y,z)
    coef1_adipose: float = 971
    coef2_adipose: float = 939
    coef1_glandular: float = 920
    coef2_glandular: float = 870

    @property
    def adipose(self):
        return {
            "tumorous": self.tumorous,
            "density": self.density,
            "radius": self.radius,
            "position": self.position,
            "coef1": self.coef1_adipose,
            "coef2": self.coef2_adipose
        }

    @property
    def glandular(self):
        return {
            "tumorous": self.tumorous,
            "density": self.density,
            "radius": self.radius,
            "position": self.position,
            "coef1": self.coef1_glandular,
            "coef2": self.coef2_glandular
        }

    @property
    def skin(self):
        return {"tumorous": False}


class MaterialProperties(ExtendedBaseModel):
    density: Annotated[float | str, FEBField("density")]
    bulk_modulus: Annotated[float | str, FEBField("k")]
    pressure_model: Annotated[float | str, FEBField("pressure_model")]
    coef1: Annotated[float, FEBField("c1")]
    coef2: Annotated[float, FEBField("c2")]

    def to_xml(self, parent, tumor: None | dict = None):
        info = self.model_fields["bulk_modulus"].metadata[0]
        ET.SubElement(parent, info.tag, **info.xml_dict).text = f"{self.bulk_modulus}"
        info = self.model_fields["pressure_model"].metadata[0]
        ET.SubElement(parent, info.tag, **info.xml_dict).text = f"{self.pressure_model}"
        if tumor['tumorous']:
            density_str = f"{self.density}+H({tumor['radius']}^2-(X-{tumor['position'][0]})^2-(Y-{tumor['position'][1]})^2-(Z-{tumor['position'][2]})^2)*{tumor['density'] - self.density}"
            info = self.model_fields['density'].metadata[0]
            ET.SubElement(parent, info.tag, type="math", **info.xml_dict).text = density_str
            coef1_str = f"{self.coef1}+H({tumor['radius']}^2-(X-{tumor['position'][0]})^2-(Y-{tumor['position'][1]})^2-(Z-{tumor['position'][2]})^2)*{tumor['coef1']}"
            info = self.model_fields['coef1'].metadata[0]
            ET.SubElement(parent, info.tag, type="math", **info.xml_dict).text = coef1_str
            coef2_str = f"{self.coef2}+H({tumor['radius']}^2-(X-{tumor['position'][0]})^2-(Y-{tumor['position'][1]})^2-(Z-{tumor['position'][2]})^2)*{tumor['coef2']} "
            info = self.model_fields['coef2'].metadata[0]
            ET.SubElement(parent, info.tag, type="math", **info.xml_dict).text = coef2_str
        else:
            info = self.model_fields['density'].metadata[0]
            ET.SubElement(parent, info.tag, **info.xml_dict).text = f"{self.density}"
            info = self.model_fields['coef1'].metadata[0]
            ET.SubElement(parent, info.tag, **info.xml_dict).text = f"{self.coef1}"
            info = self.model_fields['coef2'].metadata[0]
            ET.SubElement(parent, info.tag, **info.xml_dict).text = f"{self.coef2}"


class MaterialSettings(ExtendedBaseModel):
    """
    =======================================
    INPUT PARAMETERS NON-TUMOROUS MATERIALS
    =======================================
    For each non-tumorous tissue [skin, adipose, glandular], we assume the Mooney-Rivlin material type, which takes
    three arguments: coef1, the coefficient of the first invariant term; coef2 coefficient of second invariant term; and
    the bulk modulus. Each tissue contains the  same set of inputs listed below, though of course, different settings
    can be assigned per tissue. More for information, see: https://help.febio.org/docs/FEBioUser-4-7/UM47-4.1.2.9.html.

    - density: float [kg/m^3 > 0]       Sets the mass density.
    - bulk_modulus: float [Pa > 0]      Sets the bulk modulus in the Mooney-Rivlin material type.
    - pressure_model: str               Sets the pressure model, which should ALWAYS be set to "default".
    - coef1: float [Pa > 0]             Sets the coef1 in the Mooney-Rivlin material type.
    - coef2: float [Pa > 0]             [skin, adipose, glandular]

    The mesh, geom and tumor variables have their respective inputs. See class MeshSettings (model_settings.py), class
    GeometrySettings (model_settings.py)
    """
    skin: MaterialProperties = MaterialProperties(
        density=1100,
        bulk_modulus=480000,
        pressure_model="default",
        coef1=1200,
        coef2=1200,
    )
    adipose: MaterialProperties = MaterialProperties(
        density=911,
        bulk_modulus=425000,
        pressure_model="default",
        coef1=109,
        coef2=106,
    )
    glandular: MaterialProperties = MaterialProperties(
        density=1041,
        bulk_modulus=425000,
        pressure_model="default",
        coef1=230,
        coef2=195,
    )
    tumor: TumorProperties = TumorProperties()


class ControlSettings(ExtendedBaseModel):
    """
    This class contains all settings that are used to control the evolution of the solution and parameters for the
    nonlinear solution procedure. Details on the settings can be found on the FEBio documentation page:
    https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.1.html, though here we mention the parameters that
    allow for change and the ones should not be touched.

    For the first control step (control_step1 in class SimulationSettings), we advise not to change any of the
    parameters here. These set the incremental increase of gravity, which is strictly not relevant for the physicality
    of the animation. Therefore, the gravity steps are by default not written to the output files (.vtk). These can be
    added by settings the plot_level to PLOT_MAJOR_ITRS and the output_level to OUTPUT_MAJOR_ITRS.

    For the second control step (control_step2 in class SimulationSettings), there is more freedom for change. The
    important parameters one can play with are the time_steps and step_size. These set the total number of time steps
    and the initial step size (=dt). The step_size can be set smaller, but preferably not larger than the default value.
    The plot_level and output_level values should not be changed.
    """

    analysis: Annotated[float | str, FEBField("analysis")]
    time_steps: Annotated[float | str, FEBField("time_steps")]
    step_size: Annotated[float | str, FEBField("step_size")]
    plot_zero_state: Annotated[float | str, FEBField("plot_zero_state")]
    plot_range: Annotated[float | str, FEBField("plot_range")]
    plot_level: Annotated[float | str, FEBField("plot_level")]
    output_level: Annotated[float | str, FEBField("output_level")]
    plot_stride: Annotated[float | str, FEBField("plot_stride")]
    output_stride: Annotated[float | str, FEBField("output_stride")]
    adaptor_re_solve: Annotated[float | str, FEBField("adaptor_re_solve")]


def write_nodes_to_xml(parent, mesh):
    """
    Reads the nodes from generate_mesh.py and writes them to the .feb file.
    """
    node_elem = ET.SubElement(parent, 'Nodes', name="Object01")
    for i in range(len(mesh.nodes.tags)):
        tag = str(mesh.nodes.tags[i])
        coord = ",".join([f"{n}" for n in mesh.nodes.coords[i]])
        ET.SubElement(node_elem, "node", id=tag).text = coord


def write_elements_to_xml(parent, mesh):
    """
    Reads the elements per tissue type [skin, glandular, adipose and chest] from generate_mesh.py and writes them to
    the .feb file.

    An important detail is that for tet10 elements, the node order per element is different between gmsh and FEBio.
    This implies that some nodes' indices need to be manually adjusted to ensure proper element-node order.
    The nodes that need to be adjusted are indices 9 <-> 10 (Python index 8 <-> 9). See code below.
    """
    tissues = mesh.tissue_parts
    # This order must remain fixed
    for name in ["skin", "glandular", "adipose", "chest"]:
        tissue = getattr(tissues, name)

        if name == "chest":
            elem_elem = ET.SubElement(parent, 'Surface', name=tissue.name)
            for i in range(len(tissue.elements)):
                tag = str(int(i + 1))
                nodes_str = ",".join([f"{n}" for n in tissue.nodes[i]])
                ET.SubElement(elem_elem, tissue.type, id=tag).text = nodes_str

        else:
            elem_elem = ET.SubElement(parent, 'Elements', type=tissue.type, name=tissue.name)
            for i in range(len(tissue.elements)):
                tag = str(tissue.elements[i])
                if tissue.type == "tet10":
                    # Switch tet10 node order when converting from gmsh to FEBio
                    tissue.nodes[i][8], tissue.nodes[i][9] = tissue.nodes[i][9], tissue.nodes[i][8]
                nodes_str = ",".join([f"{n}" for n in tissue.nodes[i]])
                ET.SubElement(elem_elem, "elem", id=tag).text = nodes_str


class TimeStepperSettingsStep1(ExtendedBaseModel):
    """
    This class contains the settings that control the FEBio auto-time stepper. This auto-stime stepper will adjust the
    time step size depending on the numerical convergence stats of the previous time step. For more details, see the
    documentation: https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.2.html.

    Step 1 and step 2 are split in two distinct classes, as in the second time stepper, the 'lc'-field is connected
    to the CurveOutput.

    Here, there is one parameter that allows for change: max_retries. This sets the maximum number of
    times a time step is restarted. One can increase this number, but it should preferably not be lower than the
    default.
    """
    max_retries: Annotated[float | str, FEBField("max_retries")]
    opt_iter: Annotated[float | str, FEBField("opt_iter")]
    dtmin: Annotated[float | str, FEBField("dtmin")]
    dtmax: Annotated[float | str, FEBField("dtmax")]
    aggressiveness: Annotated[float | str, FEBField("aggressiveness")]
    cutback: Annotated[float | str, FEBField("cutback")]
    dtforce: Annotated[float | str, FEBField("dtforce")]


class TimeStepperSettingsStep2(ExtendedBaseModel):
    """
    This class contains the settings that control the FEBio auto-time stepper. This auto-stime stepper will adjust the
    time step size depending on the numerical convergence stats of the previous time step. For more details, see the
    documentation: https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.2.html.

    Step 1 and step 2 are split in two distinct classes, as in the second time stepper, the 'lc'-field is connected
    to the CurveOutput.

    Here, there is one parameter that allows for change: max_retries. This sets the maximum number of
    times a time step is restarted. One can increase this number, but it should preferably not be lower than the
    default.
    """
    max_retries: Annotated[float | str, FEBField("max_retries")]
    opt_iter: Annotated[float | str, FEBField("opt_iter")]
    dtmin: Annotated[float | str, FEBField("dtmin")]
    dtmax: Annotated[float | str, FEBField("dtmax", lc="3")]
    aggressiveness: Annotated[float | str, FEBField("aggressiveness")]
    cutback: Annotated[float | str, FEBField("cutback")]
    dtforce: Annotated[float | str, FEBField("dtforce")]


class SolverSettings(ExtendedBaseModel):
    """
    The solver settings class is an extensive list that contains detailed parameters on the solver. Here, we largely
    adopt the default settings of FEBio. For a detailed explanation of the different parameters, we refer to the
    documentation: https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.3.html.
    """
    symmetric_stiffness: Annotated[float | str, FEBField("symmetric_stiffness")]
    equation_scheme: Annotated[float | str, FEBField("equation_scheme")]
    equation_order: Annotated[float | str, FEBField("equation_order")]
    optimize_bw: Annotated[float | str, FEBField("optimize_bw")]
    lstol: Annotated[float | str, FEBField("lstol")]
    lsmin: Annotated[float | str, FEBField("lsmin")]
    lsiter: Annotated[float | str, FEBField("lsiter")]
    ls_check_jacobians: Annotated[float | str, FEBField("ls_check_jacobians")]
    max_refs: Annotated[float | str, FEBField("max_refs")]
    check_zero_diagonal: Annotated[float | str, FEBField("check_zero_diagonal")]
    zero_diagonal_tol: Annotated[float | str, FEBField("zero_diagonal_tol")]
    force_partition: Annotated[float | str, FEBField("force_partition")]
    reform_each_time_step: Annotated[float | str, FEBField("reform_each_time_step")]
    reform_augment: Annotated[float | str, FEBField("reform_augment")]
    diverge_reform: Annotated[float | str, FEBField("diverge_reform")]
    min_residual: Annotated[float | str, FEBField("min_residual")]
    max_residual: Annotated[float | str, FEBField("max_residual")]
    dtol: Annotated[float | str, FEBField("dtol")]
    etol: Annotated[float | str, FEBField("etol")]
    rtol: Annotated[float | str, FEBField("rtol")]
    rhoi: Annotated[float | str, FEBField("rhoi")]
    alpha: Annotated[float | str, FEBField("alpha")]
    beta: Annotated[float | str, FEBField("beta")]
    gamma: Annotated[float | str, FEBField("gamma")]
    logSolve: Annotated[float | str, FEBField("logSolve")]
    arc_length: Annotated[float | str, FEBField("arc_length")]
    arc_length_scale: Annotated[float | str, FEBField("arc_length_scale")]


class QnMethodSettings(ExtendedBaseModel):
    """
    The QN-method, or quasi-Newton method is a numerical solver type most solvers use within FEBio. Here we adopt the
    BFGS method and use most default values from FEBio. More information can be found in the documentation:
    https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.4.html
    """
    max_ups: Annotated[float | str, FEBField("max_ups")]
    max_buffer_size: Annotated[float | str, FEBField("max_buffer_size")]
    cycle_buffer: Annotated[float | str, FEBField("cycle_buffer")]
    cmax: Annotated[float | str, FEBField("cmax")]


class ZeroDisplacement(ExtendedBaseModel):
    """
    Boundary conditions for the chest. Here, the chest is fixed in place while gravity comes into effect; the remaining
    parts of the chest are subject to gravity and mechanical strain.
    """
    x_dof: FEBField = FEBField(tag="x_dof", val="1")
    y_dof: FEBField = FEBField(tag="y_dof", val="1")
    z_dof: FEBField = FEBField(tag="z_dof", val="1")


class PrescribedDisplacement(ExtendedBaseModel):
    """
    Boundary condition for the chest, which follows a parabolic curve. The remaining parts of the breast are subjected
    to the displacement of the chest.
    """
    dof: FEBField = FEBField(tag="dof", val="z")
    value: FEBField = FEBField(tag="value", val="1", lc="2")
    relative: FEBField = FEBField(tag="relative", val="0")


class OnlyZDisplacement(ExtendedBaseModel):
    """
    Boundary condition for the chest, which states that the chest can only move vertically (along z) during the
    parabolic displacement.
    """
    x_dof: FEBField = FEBField(tag="x_dof", val="1")
    y_dof: FEBField = FEBField(tag="y_dof", val="1")
    z_dof: FEBField = FEBField(tag="z_dof", val="0")


class BoundaryCondition(ExtendedBaseModel):
    """
    Collection of all boundary conditions into a single class.
    """
    zero_displacement: ZeroDisplacement = ZeroDisplacement()
    prescribed_displacement: PrescribedDisplacement = PrescribedDisplacement()
    only_z_displacement: OnlyZDisplacement = OnlyZDisplacement()


class Loads(ExtendedBaseModel):
    """
    Apply mass damping to body.
    """
    c: FEBField = FEBField(tag="C", val="20")


class Gravity(ExtendedBaseModel):
    """
    This function implements the points of the gravity. The first column is the running time [0,1 [s]], the second
    column the increasing fraction of the total gravity pull [0,100%], which is linear in time. By default, there are
    10 steps (n_steps = 10), but these have little effect on the actual calculation of breast. These settings are
    dictated by control_step1 in SolverSettings. Therefore, the n_steps input can safely be ignored.

    The points are then written to the .feb file.
    """
    n_steps: int = 10

    def to_xml(self, parent):
        time = np.linspace(0, 1, self.n_steps)
        loadcontroller_elem = ET.SubElement(parent, 'load_controller', id="1", name="LC1", type="loadcurve")
        ET.SubElement(loadcontroller_elem, 'interpolate').text = "LINEAR"
        ET.SubElement(loadcontroller_elem, 'extend').text = "CONSTANT"
        points_elem = ET.SubElement(loadcontroller_elem, 'points')
        for _t in time:
            string = ",".join((str(_t), str(_t)))
            ET.SubElement(points_elem, "pt").text = string


class ParabolicJump(ExtendedBaseModel):
    """
    This function implements the points of the parabolic jump after the gravity has set in, and writes them to the .feb
    file. The first column is the running time, which starts by default at t = 1 [s] - after the gravity steps -, the
    second the vertical displacement along z. The parabolic jump is derived from basic mechanics, where we assume a
    point mass only subject to gravity without resistance. The function takes two parameters:

    =================
    INPUT PARAMETERS:
    =================
    - max_height: float [m > 0]     Sets the max height of the parabolic jump. The initial velocity and total time
                                    duration is derived from max_height. This number should not be too large, else the
                                    solver has trouble with converging.
    - n_steps: int [> 1]            Sets the number of steps in which the jump is segmented, similar to n_steps in class
                                    Gravity. Though, the animation will not be evaluated at these time steps. For that,
                                    see class CurveOutput. These points are merely used for interpolation of the
                                    vertical displacement.
    """
    max_height: float = 0.01
    n_steps: int = 51

    def calculate_jump(self):
        g = 9.81  # [m/s^2]
        v_init = np.sqrt(2 * g * self.max_height)  # [m/s] initial velocity

        t_start = 1  # [s] Starting time, determined from the gravity implementation
        t_duration = 2 * v_init / g  # [s] Total duration of the parabolic trajectory
        t_end = t_start + t_duration  # [s] End time of trajectory

        time = np.linspace(t_start, t_end, self.n_steps)

        return t_duration, time, g, t_start, v_init

    def to_xml(self, parent):
        loadcontroller_elem = ET.SubElement(parent, 'load_controller', id="2", name="LC2", type="loadcurve")
        ET.SubElement(loadcontroller_elem, 'interpolate').text = "LINEAR"
        ET.SubElement(loadcontroller_elem, 'extend').text = "CONSTANT"
        points_elem = ET.SubElement(loadcontroller_elem, 'points')

        t_duration, time, g, t_start, v_init = ParabolicJump().calculate_jump()

        for t in time:
            z_displacement = -1 / 2 * g * (t - t_start) ** 2 + v_init * (t - t_start)
            string = ",".join((str(t), str(z_displacement)))
            ET.SubElement(points_elem, "pt").text = string


class Animation(ExtendedBaseModel):
    """
    This function sets the time steps at which the .vtk are outputted and writes them to the .feb file. The first column
    sets the times at which the .vtk is outputted, the second column set the dtmax: the same dtmax as  in class
    TimeStepperSettings, which it will overwrite. The function takes three arguments:
    =================
    INPUT PARAMETERS:
    =================

    - fps: int [1/s > 0]            Sets the number of frames per second for the Blender animation. The fps parameters
                                    must be equal to the fps in the Blender programme, for a physically representative
                                    animation.
    - dtmax: float [> 0]           Fixes the dtmax for every time step.

    """
    fps: int = 40
    dtmax: float = 0.01

    def to_xml(self, parent):
        # t_duration = self.duration_factor * ParabolicJump().calculate_jump()[0]

        loadcontroller_elem = ET.SubElement(parent, 'load_controller', id="3", name="LC3", type="loadcurve")
        ET.SubElement(loadcontroller_elem, 'interpolate').text = "LINEAR"
        ET.SubElement(loadcontroller_elem, 'extend').text = "CONSTANT"
        points_elem = ET.SubElement(loadcontroller_elem, 'points')

        t_start = 1
        t_duration = SimulationSettings().control_step2.time_steps * SimulationSettings().control_step2.step_size
        t_end = t_start + t_duration
        time = np.arange(t_start, t_end, 1 / self.fps)

        for t in time:
            string = ",".join((str(t), str(self.dtmax)))
            ET.SubElement(points_elem, "pt").text = string


class Output(BaseModel):
    """
    This class sets the type of output files and the information written to these files. There are five settings to pick.
    =================
    INPUT PARAMETERS:
    =================

    - output_to_xplt: bool          Setting this to TRUE outputs the simulation as a .xplt file. This is a binary file,
                                    which can only be read by FEBioStudio. The pipeline makes no use of this file.
    - output_to_vtk: bool           Setting this to TRUE outputs the simulation as a series of .vtk files, at each time
                                    step given by class CurveOutput. The .vtk files are used for the remainder of the
                                    pipeline.
    - output_displacement: bool     Settings this to TRUE writes the nodes' displacement to the .xplt/.vtk file(s). This
                                    output is used for the construction of the animation in Blender and must, therefore,
                                    always be set to TRUE.
    - output_stress: bool           Setting this to TRUE writes the elemental Cauchy stress to the x.plt/.vtk file(s).
                                    This has no further use in the remainder of the pipeline.
    - output_relative_volume: bool  Setting this to TRUE writes the relative volume to the x.plt/.vtk file(s). This
                                    output is a measure for the increase/decrease in volume of the breast with respect
                                    to its original size. This has no further use in the remainder of the pipeline.

    """
    output_to_vtk: bool = True
    output_displacement: bool = True
    output_stress: bool = False
    output_relative_volume: bool = False

    def to_xml(self, parent, filepath: Path):
        output_path = filepath.parent / "output" / filepath.stem

        if self.output_to_vtk:
            output_vtk = str(output_path.with_suffix(".vtk"))
            Outfile = ET.SubElement(parent, 'plotfile', type="vtk", file=output_vtk)
            if self.output_displacement:
                ET.SubElement(Outfile, "var", type='displacement')
            if self.output_stress:
                ET.SubElement(Outfile, "var", type='stress')
            if self.output_relative_volume:
                ET.SubElement(Outfile, "var", type='relative volume')
        else:
            output_xplt = str(output_path.with_suffix(".xplt"))
            Outfile = ET.SubElement(parent, 'plotfile', type="febio", file=output_xplt)
            if self.output_displacement:
                ET.SubElement(Outfile, "var", type='displacement')
            if self.output_stress:
                ET.SubElement(Outfile, "var", type='stress')
            if self.output_relative_volume:
                ET.SubElement(Outfile, "var", type='relative volume')



def write_xml(root, filepath: Path):
    """
    This function writes the .feb file to a predetermined filepath. The filepath must contain the correct file
    extension: ".toml". The path is created if it does not exist. The .feb file will be placed in the same folder as the
    settings file (.toml)
    """
    # Check if input "filepath" has the correct file extension (.feb)
    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"

    # Parent directory of file
    parent_path = filepath.parent
    # Create directory if it does not exist
    parent_path.mkdir(parents=True, exist_ok=True)

    # Output directory
    vtk_path = parent_path / "output"
    # Create directory for output files.
    Path(vtk_path).mkdir(parents=True, exist_ok=True)

    # Write .feb to path
    filepath_feb = Path(parent_path / filepath.stem).with_suffix(".feb")
    tree = ET.ElementTree(root)
    ET.indent(tree, space="\t", level=0)
    tree.write(filepath_feb, encoding="ISO-8859-1")

    return filepath_feb


class SimulationSettings(ExtendedBaseModel):
    """
    =================================
    INPUT PARAMETERS FEBio SIMULATION
    =================================

    This class contains all the settings to run the FEBio simulation. This includes the simulation settings (control,
    time stepper, solver and qn method), the implementation of gravity (class Gravity), the parabolic jump of the breast
    (class ParabolicJump), time settings for the output (class CurveOutput) and output settings (Output). In this
    DocString we only focus on the solver settings, details on the remaining settings can be found in their respective
    classes.

    The simulation consists of two steps: step1 and step2. Each step constitutes a number of sub-settings, which are
    "control", "time_stepper", "solver" and "qn_method". To distinguish between the settings of each step, each
    sub-setting has a suffix "_step1" or "_step2", see below.
    """
    control_step1: ControlSettings = ControlSettings(
        analysis="STATIC",
        time_steps=10,
        step_size=0.1,
        plot_zero_state="0",
        plot_range="0,-1",
        plot_level="PLOT_NEVER",
        output_level="OUTPUT_NEVER",
        plot_stride="1",
        output_stride="1",
        adaptor_re_solve="1"
    )
    timestepper_step1: TimeStepperSettingsStep1 = TimeStepperSettingsStep1(
        max_retries=40,
        opt_iter=11,
        dtmin=0,
        dtmax=0.1,
        aggressiveness=0,
        cutback=0.5,
        dtforce=0
    )
    solver_step1: SolverSettings = SolverSettings(
        symmetric_stiffness="symmetric",
        equation_scheme="staggered",
        equation_order="default",
        optimize_bw=0,
        lstol=0.9,
        lsmin=0.01,
        lsiter=5,
        ls_check_jacobians=0,
        max_refs=15,
        check_zero_diagonal=0,
        zero_diagonal_tol=0,
        force_partition=0,
        reform_each_time_step=1,
        reform_augment=0,
        diverge_reform=1,
        min_residual=1e-20,
        max_residual=0,
        dtol=0.001,
        etol=0.01,
        rtol=0,
        rhoi=-2,
        alpha=1,
        beta=0.25,
        gamma=0.25,
        logSolve=0,
        arc_length=0,
        arc_length_scale=0
    )
    qnmethod_step1: QnMethodSettings = QnMethodSettings(
        max_ups=10,
        max_buffer_size=0,
        cycle_buffer=1,
        cmax=100000
    )
    control_step2: ControlSettings = ControlSettings(
        analysis="DYNAMIC",
        time_steps=120,  # Max duration: 120 * 0.01 = 1.2 seconds
        step_size=0.01,
        plot_zero_state="0",
        plot_range="0,-1",
        plot_level="PLOT_MUST_POINTS",
        output_level="OUTPUT_MUST_POINTS",
        plot_stride="1",
        output_stride="1",
        adaptor_re_solve="1"
    )
    timestepper_step2: TimeStepperSettingsStep2 = TimeStepperSettingsStep2(
        max_retries=20,
        opt_iter=11,
        dtmin=0,
        dtmax=0.01,
        aggressiveness=0,
        cutback=0.5,
        dtforce=0
    )
    solver_step2: SolverSettings = SolverSettings(
        symmetric_stiffness="symmetric",
        equation_scheme="staggered",
        equation_order="default",
        optimize_bw=0,
        lstol=0.9,
        lsmin=0.01,
        lsiter=5,
        ls_check_jacobians=0,
        max_refs=15,
        check_zero_diagonal=0,
        zero_diagonal_tol=0,
        force_partition=0,
        reform_each_time_step=1,
        reform_augment=0,
        diverge_reform=1,
        min_residual=1e-20,
        max_residual=0,
        dtol=0.001,
        etol=0.01,
        rtol=0,
        rhoi=-2,
        alpha=1,
        beta=1,
        gamma=1.5,
        logSolve=0,
        arc_length=0,
        arc_length_scale=0
    )
    qnmethod_step2: QnMethodSettings = QnMethodSettings(
        max_ups=10,
        max_buffer_size=0,
        cycle_buffer=1,
        cmax=100000
    )
    gravity: Gravity = Gravity()
    parabolic_jump: ParabolicJump = ParabolicJump()
    animation: Animation = Animation()
    output: Output = Output()


class ModelSettings(ExtendedBaseModel):
    mesh: MeshSettings = MeshSettings()
    geometry: GeometrySettings = GeometrySettings()


class Settings(ExtendedBaseModel):
    model: ModelSettings = ModelSettings()
    material: MaterialSettings = MaterialSettings()
    simulation: SimulationSettings = SimulationSettings()
