
from pathlib import Path
import logging

import numpy as np
import pyvista as pv
from tqdm import tqdm

#  Assign the path to the single .feb file you wish to load in.


logger = logging.getLogger(__name__)
def feb_to_pointcloud(filepath: Path, obj=False):
    assert filepath.suffix == ".feb", "The input file does not have the correct file extension. Must be .feb"

    # Get name of input file
    filename = filepath.stem

    # Output directory
    filepath_output = filepath.parent / "output"
    filepath_name = filepath_output / filename
    filepath_vtk_0 = filepath_name.with_suffix(f".0.vtk")

    # Get mesh data from unperturbed breast
    vtk_mesh = pv.read(filepath_vtk_0)
    vtk_points = vtk_mesh.points  # Vertices
    vtk_mesh['orig_indices'] = np.arange(vtk_mesh.n_points, dtype = np.int32)

    # Find all displacements from vtk file
    displacement = vtk_mesh.active_vectors  # Get displacement

    # Let displacements work on initial configuration
    vtk_mesh_disp = vtk_mesh.copy()
    vtk_mesh_disp.points = vtk_mesh_disp.points + displacement

    # Extract only surface
    surfs = vtk_mesh.extract_surface(algorithm='dataset_surface', pass_pointid = True)
    surf_ids = surfs['orig_indices']

    # Remove chest wall
    chest_ids = np.where(displacement[:,0] == 0)
    front = np.setdiff1d(surf_ids, chest_ids[0])
    skin = pv.PolyData(vtk_mesh_disp.points[front])
    skin.save(filepath_name.with_suffix(f".ply"))
    if obj:
        #also save as .obj file
        skin.save(filepath_name.with_suffix(f".obj"))

if __name__ == "__main__":
    filepath = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\all_static_settings_HGO_no_tumor.feb")
    feb_to_pointcloud(filepath)
