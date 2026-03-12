from pathlib import Path
import logging

import numpy as np
import pyvista as pv
from tqdm import tqdm
from functools import partial
import feb_to_pointcloud

filepath = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\output\test_settings.obj")
dist_grid = 0.01

skin = pv.read(filepath)
bounds = np.array(skin.bounds)
n_points = np.floor(np.abs(bounds/dist_grid)).reshape(-1,2)[[0,2], :]
lines = []
n_total = np.sum(n_points)
points_x = np.range()
line1 = pv.Line((0,-1,0), (0,1,0))

