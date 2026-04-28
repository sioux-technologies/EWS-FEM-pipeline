from limols import LimolsSettings, LimolsSolver
from pathlib import Path
import numpy as np
import pyvista as pv
import logging

from pyvista import PolyData

logger = logging.getLogger(__name__)

from scripts.load_data import load_obj_file, point_clicker
from ews_fem_pipeline.prepare_simulation import Settings, write_settings_to_toml, load_settings_from_toml
from ews_fem_pipeline.cli import generate, fem
from ews_fem_pipeline.convert_simulation.feb_to_3d import feb_to_3d
import open3d as o3d

def extract_breast(skin: pv.PolyData | pv.UnstructuredGrid):
    more_points = np.array(point_clicker(skin, message='Click points around breast area ', rotation=False))
    more_points[:, 1] = 0
    breast_circumf = pv.Spline(more_points, closed=True)
    breast_area = breast_circumf.delaunay_2d()
    breast_area.translate((0, 0.5, 0), inplace=True)
    breast_volume = breast_area.extrude((0, -1, 0), capping=True)
    skin_segmented = skin.select_interior_points(breast_volume, inside_out=True)
    skin_segmented = skin_segmented.threshold(0.5)
    skin_segmented = skin_segmented.extract_surface(algorithm=None)
    return skin_segmented

def generate_projection_points(model_skin: pv.PolyData, n_points=10, n_slices = 10):
    points = np.empty((0, 2))
    for phi in np.linspace(-1 / 2 * np.pi, 1 / 2 * np.pi, n_slices, endpoint=False):
        intsect = model_skin.slice(origin=(0, 0, 0), normal=(np.cos(phi), 0, np.sin(phi)))
        ends = intsect.points[[np.argmax(intsect.points[:, 2]), np.argmin(intsect.points[:, 2])]]
        lens = np.sqrt(ends[:, 0] ** 2 + ends[:, 2] ** 2)
        ws = np.concatenate((np.linspace(0.01, lens[1], n_points, endpoint=False),
                             -1 * np.linspace(0.01, lens[0], n_points, endpoint=False)))
        points = np.append(points, np.outer(ws, np.array([np.sin(phi), -1*np.cos(phi)])), axis=0)
    return points

def project_front(surface: pv.PolyData | Path, points: np.ndarray):
    intercepts = []
    for point in points:
        projection_point = surface.ray_trace([point[0], 1, point[1]], [point[0], -1, point[1]], first_point=True)[0]
        if len(projection_point) > 0:
            intercepts.append(projection_point)
        else:
            intercepts.append([point[0], np.nan, point[1]])
            pass
    return np.array(intercepts)

def write_settings(params: np.ndarray, folder, title, settings_file: Path = None)-> Path:
    if settings_file:
        #load alternate settings
        settings = load_settings_from_toml(settings_file)
    else:
        # use default settings
        settings = Settings()
    #set fixed settings for this problem
    settings.simulation.control_step2.time_steps = float(0) #no dynamic steps
    #set input parameters as settings
    settings.model.geometry.radius_breast = float(params[0])
    settings.model.geometry.asym_p1 = float(params[1])
    settings.model.geometry.asym_p2 = float(params[2])
    settings.model.geometry.asym_p3 = float(params[3])
    settings.model.geometry.angle_nipple = float(params[4])
    filepath_out_toml = (Path(folder) / title).with_suffix('.toml')
    write_settings_to_toml(filepath=filepath_out_toml, settings=settings)
    return filepath_out_toml

def breast_analysis(params, folder, title, skin):
    breast_model_obj = run_breast_model(params, folder, title)
    breast_surface = load_obj_file(breast_model_obj, switch_axes=False)
    residuals = compare_geometries(breast_surface, skin)
    return residuals

def run_breast_model(params, folder, title) -> Path:
    output_title = f"{params[0]*1000:.0f}-{params[1]*1000:.0f}-{params[2]*1000:.0f}-{params[3]*1000:.0f}-{params[4]*10:.0f}"
    if (Path(folder/'defaults'/output_title).with_suffix('.obj')).is_file():
        obj_files = Path(folder/'defaults'/output_title).with_suffix('.obj')
    else:
        # Write parameters to settings file
        filepath_out_toml = write_settings(params, folder/title, output_title)

        # Generate mesh, run, and generate displaced mesh .obj file
        mesh_files = generate.callback([filepath_out_toml])
        feb_files = fem.callback(mesh_files, jobs=0)
        obj_files = feb_to_3d(feb_files[0])
    return obj_files

def compare_geometries(breast_model_geom: pv.PolyData, breast_target_geom: pv.PolyData, n_points: int =10, n_slices: int = 10) \
        -> np.ndarray:
    # Load model mesh
    center_breast(breast_model_geom, nipple_coord = breast_model_geom.points[np.argmax(breast_model_geom.points[:, 1])])
    #Project projection points on model mesh
    breast_model_geom= breast_model_geom.extract_surface(algorithm=None)
    projection_points = generate_projection_points(breast_model_geom, n_points, n_slices)
    projected_model = project_front(breast_model_geom, projection_points)

    #Load both clouds into open3d
    pcd_model = o3d.geometry.PointCloud()
    pcd_model.points = o3d.utility.Vector3dVector(np.array(projected_model))
    pcd_target = o3d.geometry.PointCloud()
    pcd_target.points = o3d.utility.Vector3dVector(np.array(breast_target_geom.points))

    # compute transformation and SE
    reg_p2p = o3d.pipelines.registration.registration_icp(pcd_model, pcd_target, 0.1)
    correspondence = np.array(reg_p2p.correspondence_set)
    sq_err = np.sum(np.square(np.array(pcd_model.points)[correspondence[:, 0]] - np.array(pcd_target.points)[correspondence[:, 1]]), axis=1)
    return sq_err

def show_results(folder: Path, skin_segmented: PolyData, title: str):
    model_skin_final = (load_obj_file((Path(folder) / 'output' / title).with_suffix('.obj')))
    center_breast(model_skin_final, nipple_coord=model_skin_final.points[np.argmax(model_skin_final.points[:, 1])])

    plotter = pv.Plotter()
    plotter.add_axes()
    plotter.view_xz()
    plotter.add_mesh(model_skin_final, opacity=0.8, color='yellow')
    plotter.add_mesh(skin_segmented, opacity=0.8, color='blue')
    plotter.show()


def prepare_data(filepath) -> PolyData:
    # Import target surface and determine center (nipple)
    skin = load_obj_file(filepath, scale=0.2,
                         switch_axes=True)  # data is not to scale, hence the 0.2 (guesstimated)
    # Translate such that the nipple is at the origin
    center_breast(skin)
    # Segment the breast and get projection points
    skin_segmented = extract_breast(skin)
    return skin_segmented


def center_breast(skin: pv.PolyData | pv.UnstructuredGrid, nipple_coord: tuple = None):
    if nipple_coord is None:
        # Translate such that the nipple is at the origin
        nipple_coord = point_clicker(skin, message='Click point for nipple. ')[0]
        skin.translate(-1 * nipple_coord, inplace=True)
    else:
        skin.translate(-1*nipple_coord, inplace=True)
    nipple_normal = find_area_normal(skin, radius = 0.02, center=(0,0,0))
    nipple_normal[2] = 0
    nipple_normal = nipple_normal/np.linalg.norm(nipple_normal)
    rot_axis = np.cross(nipple_normal, (0, 1, 0))
    rot_axis = rot_axis / np.linalg.norm(rot_axis)
    rot_angle = np.degrees(np.arccos(np.dot(nipple_normal, (0, 1, 0))))
    skin.rotate_vector(vector=rot_axis, angle=rot_angle, inplace=True)


def find_area_normal(skin: pv.PolyData | pv.UnstructuredGrid, radius: float, center: tuple = (0, 0, 0)) -> np.ndarray:
    search_volume = pv.Sphere(radius=radius, center=center)
    search_area = skin.select_interior_points(search_volume, inside_out=False)
    search_area = search_area.threshold(0.5)
    search_area = search_area.extract_surface(algorithm=None)
    nipple_normal = np.average(search_area.compute_normals()['Normals'], axis=0)
    nipple_normal = nipple_normal / np.linalg.norm(nipple_normal)
    return nipple_normal

def run_optimization(filepath: Path, folder: Path|None = None, params_0: np.ndarray = np.array([0.07, 0, 0, 0, 22.5]),
                     n_points: int = 10, n_slices: int = 10):
    ### Prepare input data
    skin_segmented = prepare_data(filepath)

    # Prepare settings and output files
    title = filepath.stem
    if folder == None:
        folder = filepath.parent
    output_folder = folder / title

    ### Run model simulations
    settings_limols = LimolsSettings(x0=params_0, n_residuals=n_points * n_slices * 2,
                                     scale=np.array([0.15, 0.5, 0.1, 0.1, 90]),
                                     xu=np.array([0.15, 1, 1, 1, 45]), xl=np.array([0, -1, -1, -1, 0]),
                                     maxfev=150)
    solver = LimolsSolver(settings_limols)

    parameter, expected_residual, step_size = solver.get_initial_step()
    # 1st step
    residual = breast_analysis(parameter, output_folder, title, skin_segmented)
    parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)
    # 2nd to last step
    while not solver.done:
        residual = breast_analysis(parameter, output_folder, title, skin_segmented)
        parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)

    show_results(folder, skin_segmented, title)

if __name__ == "__main__":
    ### User inputs
    filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3043_01_lr.frame_001.obj")
    n_points = 10
    n_slices = 10
    folder = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\optimization")
    run_optimization(filepath, folder)
