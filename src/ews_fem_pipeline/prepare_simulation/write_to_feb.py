import xml.etree.ElementTree as ET
from pathlib import Path

from ews_fem_pipeline.prepare_simulation.model_settings import MeshParts
from ews_fem_pipeline.prepare_simulation.simulation_settings import (
    BoundaryCondition,
    Constants,
    FEBElement,
    Loads,
    Settings,
    write_elements_to_xml,
    write_nodes_to_xml,
    write_xml,
)


def write_to_feb(filepath: Path, mesh: MeshParts, settings: Settings):
    """
    This file writes the mesh and simulation settings to the .xml/.feb file using the settings from simulation_settings.py
    """


    FEB_element = FEBElement()
    ###############################################################################################################
    # Root #
    ########
    root = ET.Element('febio_spec', version="4.0")

    FEB_element.module.to_xml(parent=root)

    ##############################################################################################################
    # Globals #
    ###########
    globals_elem = FEB_element.globals.to_xml(parent=root)

    ##############################################################################################################
    # Constants #
    #############
    constants_elem = FEB_element.constants.to_xml(parent=globals_elem)
    Constants().to_xml(parent=constants_elem)

    #################################################################################################################
    # Materials #
    #############
    material_elem = FEB_element.material.to_xml(parent=root)

    skin_elem = FEB_element.skin.to_xml(parent=material_elem)
    settings.material.skin.to_xml(parent=skin_elem, tumor=settings.material.tumor.skin)

    adipose_elem = FEB_element.adipose.to_xml(parent=material_elem)
    settings.material.adipose.to_xml(parent=adipose_elem, tumor=settings.material.tumor.adipose)

    glandualar_elem = FEB_element.glandular.to_xml(parent=material_elem)
    settings.material.glandular.to_xml(parent=glandualar_elem, tumor=settings.material.tumor.glandular)

    #################################################################################################################
    # Mesh #
    ########
    mesh_elem = FEB_element.mesh.to_xml(parent=root)

    # Nodes
    write_nodes_to_xml(parent=mesh_elem, mesh=mesh)

    # Elements
    write_elements_to_xml(parent=mesh_elem, mesh=mesh)

    # Mass damping and gravity
    FEB_element.mass_damping.to_xml(parent=mesh_elem)
    FEB_element.gravitational_acceleration.to_xml(parent=mesh_elem)

    #################################################################################################################
    # Mesh domains #
    ################
    mesh_domains_elem = FEB_element.mesh_domains.to_xml(parent=root)

    # Shell domain
    shell_elem = FEB_element.shell_domain.to_xml(parent=mesh_domains_elem)
    FEB_element.shell_thickness.to_xml(parent=shell_elem)

    # Solid domain
    FEB_element.solid_domain_glandular.to_xml(parent=mesh_domains_elem)
    FEB_element.solid_domain_adipose.to_xml(parent=mesh_domains_elem)

    # Loads
    loads_elem = FEB_element.loads.to_xml(parent=root)

    body_load_elem = FEB_element.body_load1.to_xml(parent=loads_elem)
    FEB_element.force.to_xml(parent=body_load_elem)

    #################################################################################################################
    # Steps #
    #########
    step_elem = FEB_element.step.to_xml(parent=root)

    #################################################################################################################
    # Step 1 #
    ##########
    step1_elem = FEB_element.step1.to_xml(parent=step_elem)

    # Control
    control1_elem = FEB_element.control.to_xml(parent=step1_elem)
    settings.simulation.control_step1.to_xml(parent=control1_elem)

    # Time Stepper
    timestepper1_elem = FEB_element.time_stepper.to_xml(parent=control1_elem)
    settings.simulation.timestepper_step1.to_xml(parent=timestepper1_elem)

    # Solver
    solver1_elem = FEB_element.solver.to_xml(parent=control1_elem)
    settings.simulation.solver_step1.to_xml(parent=solver1_elem)

    # qn_method
    qnmethod1_elem = FEB_element.qn_method.to_xml(parent=solver1_elem)
    settings.simulation.qnmethod_step1.to_xml(parent=qnmethod1_elem)

    # Boundary
    boundary1_elem = FEB_element.boundary.to_xml(parent=step1_elem)
    boundary1_field = FEB_element.boundary_zero_displacement.to_xml(parent=boundary1_elem)
    BoundaryCondition().zero_displacement.to_xml(parent=boundary1_field)

    #################################################################################################################
    # Step 2 #
    ##########
    step2_elem = FEB_element.step2.to_xml(parent=step_elem)

    # Control
    control2_elem = FEB_element.control.to_xml(parent=step2_elem)
    settings.simulation.control_step2.to_xml(parent=control2_elem)

    # Time Stepper
    timestepper2_elem = FEB_element.time_stepper.to_xml(parent=control2_elem)
    settings.simulation.timestepper_step2.to_xml(parent=timestepper2_elem)

    # Solver
    solver2_elem = FEB_element.solver.to_xml(parent=control2_elem)
    settings.simulation.solver_step2.to_xml(parent=solver2_elem)

    # qn_method
    qnmethod2_elem = FEB_element.qn_method.to_xml(parent=solver2_elem)
    settings.simulation.qnmethod_step2.to_xml(parent=qnmethod2_elem)

    # Boundary
    boundary2_elem = FEB_element.boundary.to_xml(parent=step2_elem)

    boundary2_field = FEB_element.boundary_parabolic_trajectory.to_xml(parent=boundary2_elem)
    BoundaryCondition().prescribed_displacement.to_xml(parent=boundary2_field)

    boundary2_field = FEB_element.boundary_only_z_displacement.to_xml(parent=boundary2_elem)
    BoundaryCondition().only_z_displacement.to_xml(parent=boundary2_field)

    # Loads
    loads2_elem = FEB_element.loads.to_xml(parent=step2_elem)
    bodyload2_elem = FEB_element.body_load2.to_xml(parent=loads2_elem)
    Loads().to_xml(parent=bodyload2_elem)

    #################################################################################################################
    # Load Data #
    #############
    loaddata_elem = FEB_element.load_data.to_xml(parent=root)

    # Load Controller |points for increasing gravity
    settings.simulation.gravity.to_xml(parent = loaddata_elem)

    # Load Controller | points for parabola trajectory of breast
    settings.simulation.parabolic_jump.to_xml(parent = loaddata_elem)

    # Load Controller | points for output
    settings.simulation.animation.to_xml(parent = loaddata_elem)

    #################################################################################################################
    # Output #
    ##########
    output_elem = FEB_element.output.to_xml(parent=root)
    settings.simulation.output.to_xml(parent=output_elem, filepath=filepath)

    #################################################################################################################
    # Write to .feb #
    #################

    write_xml(root=root, filepath=filepath)
