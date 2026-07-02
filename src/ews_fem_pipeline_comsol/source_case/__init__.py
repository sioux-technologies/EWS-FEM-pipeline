from ews_fem_pipeline_comsol.source_case.geometry_settings import (
    GeometrySettings,
    MeshParts,
    MeshSettings,
)
from ews_fem_pipeline_comsol.source_case.source_case_settings import (
    BoundaryCondition,
    Constants,
    Settings,
    SourceElement,
    write_elements_to_xml,
    write_nodes_to_xml,
    write_xml,
)
from ews_fem_pipeline_comsol.source_case.toml_io import (
    load_settings_from_toml,
    write_settings_to_toml,
)


def generate_mesh(*args, **kwargs):
    from ews_fem_pipeline_comsol.source_case.mesh_generation import generate_mesh as _generate_mesh

    return _generate_mesh(*args, **kwargs)
