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

# Get mesh data from unperturbed breast
vtk_mesh = pv.read(filepath_vtk_0)
vtk_points = vtk_mesh.points  # Vertices

# Find all displacements from vtk file
displacement = vtk_mesh.active_vectors  # Get displacement

# Let displacements work on initial configuration
vtk_mesh_disp = vtk_mesh
vtk_mesh_disp.points = vtk_points + displacement

# Extract only surface
surfs = vtk_mesh_disp.extract_surface(algorithm='dataset_surface')
surf_ids = surfs['vtkOriginalPointIds']
chest_ids = np.where(displacement[:,0] == 0)
front_ids = np.setdiff1d(surf_ids, chest_ids)

#Now contains both skin and glandular surfaces. Extract only skin surface
skin_mesh = surfs.connectivity(extraction_mode='largest')
skin_points = skin_mesh.points

