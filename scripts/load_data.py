from pathlib import Path
import pyvista as pv
from functools import partial
import numpy as np

#  Assign the path to the folder of data you wish to load in.

def load_obj_file(filepath: Path, switch_axes = False, scale=None) -> pv.UnstructuredGrid:
    skin = pv.read(filepath)
    if switch_axes:
        skin.points[:, [0,1,2]] = skin.points[:,[2,0,1]] #swap x- and y-axis to match model output
    if scale is not None:
        skin.points = scale*skin.points
    return skin

def point_clicker(skin: pv.PolyData | pv.UnstructuredGrid, message : str = "", rotation=True) -> list:
    clicked_points = []
    point_temp = None
    def point_selector(point):
        nonlocal point_temp
        point_temp = point
        print('Point picked: ', str(point), '. Press enter to confirm.')

    def point_saver(picked_points):
        nonlocal point_temp
        picked_points.append(point_temp)
        print('Point', str(point_temp), ' confirmed. Select another point or press Q to exit.')
        point_temp = tuple(point_temp)
        pl.add_points(np.array(point_temp), render_points_as_spheres=True, color = 'red', point_size=10)
        pl.render()

    wrapped_point_saver = partial(point_saver, picked_points=clicked_points)
    pl=pv.Plotter()
    if not rotation:
        pl.enable_custom_trackball_style(left = 'pan', right = 'pan', control_left='pan', control_right='pan')
    pl.add_mesh(skin)
    pl.enable_point_picking(callback=point_selector, picker = 'point',
                                    show_message=message + 'press enter to confirm, press Q when done.',
                                    left_clicking=True)
    pl.add_key_event('Return', wrapped_point_saver)
    pl.view_xz(negative=True)
    pl.enable_parallel_projection()
    pl.show()

    return clicked_points


if __name__ == "__main__":
    filepath = Path(
        r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3032_01_lr.frame_001.obj")
    point_clicker(filepath)