import numpy as np
from pathlib import Path
import logging

import pyvista as pv
from tqdm import tqdm

logger = logging.getLogger(__name__)


def feb_to_blender(filepath: Path):  # Input should be path to .vtk files

    assert filepath.suffix == ".feb", "The input file does not have the correct file extension. Must be .feb"

    # Get name of input file
    filename = filepath.stem

    # Output directory
    filepath_output = filepath.parent / "output"
    filepath_name = filepath_output / filename

    # Find all .vtk files in /output.
    # .vtk files are named: <filename>.idx.vtk

    idx: int = 0
    filepath_vtk = filepath_name.with_suffix(f".{idx}.vtk")

    filepaths_vtk = []
    while filepath_vtk.exists():
        filepaths_vtk.append(filepath_vtk)
        idx += 1
        filepath_vtk = filepath_name.with_suffix(f".{idx}.vtk")
    logger.info(f"Found {idx + 1} .vtk files")

    # Define paths output .obj file for surface mesh and output .npy file for displacements
    filepath_obj = (filepath_output / filename).with_suffix(".obj")
    filepath_npy = (filepath_output / filename).with_suffix(".npy")

    # Define number of time stamps
    num_vtk = len(filepaths_vtk)
    time_stamps = np.linspace(0, num_vtk - 1, num_vtk)

    # Get mesh data from unperturbed breast
    vtk_mesh = pv.read(filepaths_vtk[0])
    vtk_points = vtk_mesh.points  # Vertices

    # Save unperturbed .vtk file as .obj file to be later read by Blender
    pl = pv.Plotter()
    pl.add_mesh(vtk_mesh)
    pl.export_obj(filename=filepath_obj)
    logger.info(f"Saving unperturbed mesh as .obj file at: {filepath_obj}.")

    # Read obj file using PyVista
    obj_mesh = pv.read(filepath_obj)
    obj_points = obj_mesh.points

    # Define number of vertices at surface
    len_surface_points = len(obj_points)

    # Obj file only contains surface of mesh,
    # so first find indices of full mesh in .vtk that correspond with the surface.

    # Reshape vertices points, changing each row to a tuple of values. Then the matrix becomes a 1D array
    # With that, we can make use of the 1D intersection

    obj_points_view = obj_points.view([('', obj_points.dtype)] * obj_points.shape[1])
    vtk_points_view = vtk_points.view([('', vtk_points.dtype)] * vtk_points.shape[1])

    # Find intersection of the two '1D' arrays and retrieve the indices as well
    intersected, obj_idx, vtk_idx = np.intersect1d(obj_points_view, vtk_points_view, return_indices=True)

    # Sort obj indices' indices from low to high, as obj follows this order
    sort_idx = obj_idx.argsort()

    # Only thing we need from the obj are these indices.
    # We assume that the index order is the same for all obj files
    # This is where we start looping over the different .vtk files to extract the displacement

    # Initialize 3D array containing all displacements per time step
    surface_disp_obj = np.zeros((len(time_stamps), len_surface_points, 3))

    for idx_time, time_step in enumerate(tqdm(time_stamps)):
        file_path = filepaths_vtk[idx_time]

        shifted_grid = pv.read(file_path)
        displacement = shifted_grid.active_vectors  # Get displacement

        # All surface vertices. Full displacement array follows order of points
        # But surface displacement array needs to follow order of obj
        surface_disp = displacement[vtk_idx]

        # Now assign sorted indices to surface
        surface_disp_obj[idx_time] = surface_disp[sort_idx]

    # Save data to binary .npy file file
    np.save(str(filepath_npy), surface_disp_obj)
    logger.info(f"Saving displacements: {filepath_npy}.")
