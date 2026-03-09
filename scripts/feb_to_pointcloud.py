################################################################################################
# The following script should be opened within the Blender python API. That is the 'scripting' #
# section in the top ribbon. Make sure that the paths are set up correctly, by changing the    #
# input for "filepath".                                                                        #
################################################################################################

from pathlib import Path

import numpy as np

#  Assign the path to the single .feb file you wish to load in.
filepath = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\all_static_settings.feb")

import logging
from pathlib import Path

import numpy as np
import pyvista as pv
from tqdm import tqdm

logger = logging.getLogger(__name__)


assert filepath.suffix == ".feb", "The input file does not have the correct file extension. Must be .feb"

# Get name of input file
filename = filepath.stem

# Output directory
filepath_output = filepath.parent / "output"
filepath_name = filepath_output / filename
filepath_vtk_0 = filepath_name.with_suffix(f".0.vtk")

# Define paths output .obj file for surface mesh and output .npy file for displacements
filepath_obj = (filepath_output / filename).with_suffix(".obj")
filepath_npy = (filepath_output / filename).with_suffix(".npy")

# Get mesh data from unperturbed breast
vtk_mesh = pv.read(filepath_vtk_0)
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

# Find all displacements from vtk file
displacement = vtk_mesh.active_vectors  # Get displacement

# All surface vertices. Full displacement array follows order of points
# But surface displacement array needs to follow order of obj
surface_disp = displacement[vtk_idx]

# Now assign sorted indices to surface
surface_disp_obj = surface_disp[sort_idx]

# Let displacements work on initial configuration
pos_gravity = obj_points-surface_disp_obj
