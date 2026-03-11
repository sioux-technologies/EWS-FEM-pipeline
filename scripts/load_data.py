from pathlib import Path
import logging

import numpy as np
import pyvista as pv
from tqdm import tqdm
from functools import partial

#  Assign the path to the folder of data you wish to load in.
filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3032.01.lr.frame_001.obj")
skin = pv.read(filepath)
skin.points[:, [0,1]] = skin.points[:,[1,0]] #swap x- and y-axis to match model output

picked_points = []
nipple_coord_temp = None
def point_selecter(_point):
    global nipple_coord_temp
    nipple_coord_temp = _point
    print('Point picked: ', str(_point), '. Press enter to confirm.')

def point_saver(picked_points):
    global nipple_coord_temp
    picked_points.append(nipple_coord_temp)
    print('Point Confirmed. Select another point or press Q to exit.')

wrapped_point_saver = partial(point_saver, picked_points=picked_points)
pl=pv.Plotter()
pl.add_mesh(skin)
picked_point = pl.enable_point_picking(callback=point_selecter, picker = 'point',
                                show_message='Pick a point for nipple, press enter to confirm, press Q when done.',
                                left_clicking=True)
pl.add_key_event('Return', wrapped_point_saver)
pl.view_zx()
pl.show()

nipple_point = picked_points[0]
