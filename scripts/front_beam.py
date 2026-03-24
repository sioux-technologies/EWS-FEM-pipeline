from pathlib import Path

import numpy as np
import pyvista as pv
from load_data import load_obj_file, point_clicker
from ews_fem_pipeline.prepare_simulation import Settings, write_settings_to_toml
from ews_fem_pipeline.prepare_simulation import generate_mesh, write_to_feb
from ews_fem_pipeline.cli import generate, fem
from ews_fem_pipeline.convert_simulation.feb_to_3d import feb_to_3d


def extract_breast(skin: pv.PolyData | pv.UnstructuredGrid):
    more_points = np.array(point_clicker(skin, message='Click points around breast area '))
    more_points[:, 1] = 0
    breast_circumf = pv.Spline(more_points, closed=True)
    breast_area = breast_circumf.delaunay_2d()
    breast_area.translate((0, 0.5, 0), inplace=True)
    breast_volume = breast_area.extrude((0, -1, 0), capping=True)
    skin_segmented = skin.select_interior_points(breast_volume, inside_out=True)
    skin_segmented = skin_segmented.threshold(0.5)
    skin_segmented = skin_segmented.extract_surface(algorithm=None)
    return skin_segmented


def projection_points(skin_segmented: pv.PolyData, m=15, dist_points=0.01):
    intercepts = []
    points = np.empty((0, 2))
    bounds = np.array(skin_segmented.bounds)
    n = int(np.floor(np.max(np.abs(bounds)) / dist_points))
    for theta in np.linspace(0, 2 * np.pi, m, endpoint=False):
        for ring in range(n):
            x = ring * dist_points * np.sin(theta)
            z = ring * dist_points * np.cos(theta)
            projection_point = skin_segmented.ray_trace([x, 1, z], [x, -1, z], first_point=True)[0]
            if len(projection_point) > 0:
                intercepts.append(projection_point)
                points = np.append(points, np.array([x, z]).reshape(1, -1), axis=0)
    return points, intercepts


def project_front(surface: pv.PolyData | Path, points: np.ndarray):
    intercepts = []
    for point in points:
        projection_point = surface.ray_trace([point[0], 1, point[1]], [point[0], -1, point[1]], first_point=True)[0]
        if len(projection_point) > 0:
            intercepts.append(projection_point)
        else:
            intercepts.append([np.nan, np.nan, np.nan])
    return intercepts


def match_settings(skin: pv.PolyData):
    bounds = np.array(skin.bounds)
    settings = Settings()
    settings.model.geometry.radius_breast = float(np.abs((bounds[2] - bounds[3])))
    settings.model.geometry.radius_nipple = float(0.01)
    settings.model.mesh.order = 1
    settings.simulation.control_step2.time_steps = float(0)
    return settings

if __name__ == "__main__":

    filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3032_01_lr.frame_001.obj")
    skin = load_obj_file(filepath)
    nipple_coord = point_clicker(skin, message='Click point for nipple')

    #translate such that the nipple is at the origin
    skin_pd = pv.PolyData(skin.points)
    skin_pd.translate(-1*nipple_coord[0], inplace=True)
    skin.points = skin_pd.points*0.25

    skin_segmented = extract_breast(skin)
    points, projected_real = projection_points(skin_segmented)
    settings = match_settings(skin_segmented)

    folder = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\optimization")
    filepath_out = Path(folder) / filepath.stem
    filepath_out_toml = filepath_out.with_suffix(f'.toml')
    write_settings_to_toml(filepath = filepath_out_toml, settings = settings)

    mesh_files = generate.callback([filepath_out_toml])
    feb_files = fem.callback(mesh_files, jobs=0)
    obj_files = feb_to_3d(feb_files[0])

    surface = load_obj_file(obj_files, switch_axes=False)
    surface.translate([0, -surface.bounds[3]], inplace=True)
    surface= surface.extract_surface(algorithm=None)
    projected_model = project_front(surface, points)

    plotter = pv.Plotter()
    plotter.add_axes()
    plotter.add_points(np.array(projected_model), color="red")
    plotter.add_points(np.array(projected_real), color="blue")
    plotter.add_points(np.array([0,0,0]), color="green")
    plotter.show()

