from pathlib import Path

import numpy as np
import pyvista as pv
from load_data import load_obj_file, point_clicker
from ews_fem_pipeline.prepare_simulation import Settings, write_settings_to_toml
from ews_fem_pipeline.prepare_simulation import generate_mesh, write_to_feb
from ews_fem_pipeline.cli import generate, fem
from ews_fem_pipeline.convert_simulation.feb_to_3d import feb_to_3d

def extract_breast(skin: pv.PolyData | pv.UnstructuredGrid):
    more_points = np.array(point_clicker(skin, message = 'Click points around breast area '))
    more_points[:, 1] = 0
    breast_circumf = pv.Spline(more_points, closed=True)
    breast_area = breast_circumf.delaunay_2d()
    breast_area.translate((0, 0.5, 0), inplace=True)
    breast_volume = breast_area.extrude((0, -1, 0), capping=True)
    skin_segmented = skin.select_interior_points(breast_volume, inside_out=True)
    skin_segmented = skin_segmented.threshold(0.5)
    skin_segmented = skin_segmented.extract_surface(algorithm=None)
    return skin_segmented

# filepath = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\output\all_static_settings_HGO_no_tumor.obj")
filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3032_01_lr.frame_001.obj")
skin = load_obj_file(filepath)
nipple_coord = point_clicker(skin, message='Click point for nipple')

#translate such that the nipple is at the origin
skin_pd = pv.PolyData(skin.points)
skin_pd.translate(-1*nipple_coord[0], inplace=True)
skin.points = skin_pd.points*0.25

skin_segmented = extract_breast(skin)

dist_grid = 0.01
bounds = np.array(skin_segmented.bounds)
m = 15
n = int(np.floor(np.max(np.abs(bounds))/dist_grid))
lines = []
inters = []
for theta in np.linspace(0,2*np.pi, m, endpoint=False):
    for ring in range(n):
        x = ring*dist_grid*np.sin(theta)
        z = ring*dist_grid*np.cos(theta)
        projection_point = skin_segmented.ray_trace([x, 1, z], [x, -1, z], first_point=True)[0]
        if len(projection_point)>0:
            inters.append(projection_point)
        else:
            inters.append([np.nan, np.nan, np.nan])

settings=Settings()
settings.model.geometry.radius_breast = float(np.abs((bounds[2]-bounds[3])))
settings.model.geometry.radius_nipple = float(0.01)
settings.simulation.control_step2.time_steps = float(0)
folder = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\optimization")
filepath_out = Path(folder) / filepath.stem
filepath_out_toml = filepath_out.with_suffix(f'.toml')
write_settings_to_toml(filepath = filepath_out_toml, settings = settings)

mesh_files = generate.callback([filepath_out_toml])
feb_files = fem.callback(mesh_files, jobs=0)
feb_to_3d(feb_files)