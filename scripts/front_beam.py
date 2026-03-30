from limols import LimolsSettings, LimolsSolver
import copy
from pathlib import Path
import numpy as np
import pyvista as pv
from pyvista import raise_has_duplicates
import logging
logger = logging.getLogger(__name__)

from load_data import load_obj_file, point_clicker
from ews_fem_pipeline.prepare_simulation import Settings, write_settings_to_toml
from ews_fem_pipeline.cli import generate, fem
from ews_fem_pipeline.convert_simulation.feb_to_3d import feb_to_3d
import open3d as o3d

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

def generate_projection_points(skin_segmented: pv.PolyData, dist_points=0.01):
    intercepts = []
    points = np.empty((0, 2))
    bounds = np.array(skin_segmented.bounds)
    n = int(np.floor(np.max(np.abs(bounds)) / dist_points))
    for ring in range(n):
        m = int(np.floor(2*np.pi*ring))
        for theta in np.linspace(0, 2 * np.pi, m, endpoint=False):
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
def write_settings(params: np.ndarray, folder, title):
    settings = Settings()
    #set fixed settings for this problem
    settings.model.geometry.radius_nipple = float(0.0075)
    settings.model.mesh.order = 1
    settings.simulation.control_step2.time_steps = float(0)
    #set variable settings
    settings.model.geometry.radius_breast = float(params[0])
    settings.model.geometry.asym_p1 = float(params[1])
    settings.model.geometry.asym_p2 = float(params[2])
    settings.model.geometry.asym_p3 = float(params[3])
    settings.model.geometry.angle_nipple = float(params[4])
    filepath_out_toml = (Path(folder) / title).with_suffix('.toml')
    write_settings_to_toml(filepath=filepath_out_toml, settings=settings)
    return filepath_out_toml



def breast_model(params, projected_real, points, folder, title):
    # Write parameters to settings file
    filepath_out_toml = write_settings(params, folder, title)

    # Generate mesh, run, and generate displaced mesh .obj file
    mesh_files = generate.callback([filepath_out_toml])
    feb_files = fem.callback(mesh_files, jobs=0)
    obj_files = feb_to_3d(feb_files[0])

    # Load resulting mesh
    surface = load_obj_file(obj_files, switch_axes=False)
    # Translate to have nipple at (0,0,0)
    surface.translate(-1*surface.points[np.argmax(surface.points[:,1])], inplace=True)
    #Project projection points on model mesh
    surface= surface.extract_surface(algorithm=None)
    projected_model = project_front(surface, points)

    #Load both clouds into open3d
    pcd_model = o3d.geometry.PointCloud()
    pcd_model.points = o3d.utility.Vector3dVector(np.array(projected_model))
    pcd_target = o3d.geometry.PointCloud()
    pcd_target.points = o3d.utility.Vector3dVector(np.array(projected_real))

    # compute transformation and SE
    correspondence = o3d.utility.Vector2iVector(np.repeat(np.where(np.sum(projected_real, axis=1) != np.nan), 2)
                                                .reshape(-1, 2))
    estimator = o3d.pipelines.registration.TransformationEstimationPointToPoint()
    transformation = estimator.compute_transformation(pcd_model, pcd_target, correspondence)
    pcd_model.transform(transformation)
    sq_err = np.sum(np.square(np.array(pcd_target.points) - np.array(pcd_model.points)), axis=1)
    return sq_err

    # return residuals
if __name__ == "__main__":
    ### Prepare input data
    # Import target surface and determine center (nipple)
    filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3032_01_lr.frame_001.obj")
    skin = load_obj_file(filepath, scale = 0.2) #data is not to scale, hence the 0.2 (guesstimated)

    # Translate such that the nipple is at the origin
    nipple_coord = point_clicker(skin, message='Click point for nipple. ')
    skin.translate(-1*nipple_coord[0], inplace=True)

    # Segment the breast and get projection points
    skin_segmented = extract_breast(skin)
    points, projected_real = generate_projection_points(skin_segmented)

    # Prepare settings and output files
    folder = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\optimization")
    title = filepath.stem

    # first guess for radius and write settings
    bounds = np.array(skin.bounds)
    guess_radius_breast = float(1/2*np.abs((bounds[0] - bounds[1])))
    params = np.array([guess_radius_breast, 0, 0, 0, 0])

    ### Run model simulations
    settings_limols = LimolsSettings(x0=params, n_residuals=len(points), scale = np.array([0.1, 0.1, 0.1, 0.1, 40]),
                                     xu=np.array([0.15, 1, 1, 1, 45]), xl = np.array([0, -1, -1, -1, 0]))
    solver = LimolsSolver(settings_limols)

    parameter, expected_residual, step_size = solver.get_initial_step()
    #1st step
    residual = breast_model(parameter, projected_real, points, folder, title)
    parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)
    #2nd step
    while not solver.done:
        residual = breast_model(parameter, projected_real, points, folder, title)
        parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)
    # # Generate mesh, run, and generate displaced mesh .obj file
    # mesh_files = generate.callback([filepath_out_toml])
    # feb_files = fem.callback(mesh_files, jobs=0)
    # obj_files = feb_to_3d(feb_files[0])
    #
    # # Load resulting mesh
    # surface = load_obj_file(obj_files, switch_axes=False)
    # # Translate to have nipple at (0,0,0)
    # surface.translate(-1*surface.points[np.argmax(surface.points[:,1])], inplace=True)
    # #Project projection points on model mesh
    # surface= surface.extract_surface(algorithm=None)
    # projected_model = project_front(surface, points)
    #
    # #Load both clouds into open3d
    # pcd_model = o3d.geometry.PointCloud()
    # pcd_model.points = o3d.utility.Vector3dVector(np.array(projected_model))
    # pcd_target = o3d.geometry.PointCloud()
    # pcd_target.points = o3d.utility.Vector3dVector(np.array(projected_real))
    #
    # # compute initial RMSE and transformation
    # correspondence = o3d.utility.Vector2iVector(np.repeat(np.where(np.sum(projected_real, axis=1) != np.nan), 2).reshape(-1, 2))
    # estimator = o3d.pipelines.registration.TransformationEstimationPointToPoint()
    # print(estimator.compute_rmse(pcd_target, pcd_model, correspondence))
    # transformation = estimator.compute_transformation(pcd_model, pcd_target, correspondence)
    #
    # # Copy model cloud and transform
    # pcd_model_trans = copy.deepcopy(pcd_model).transform(transformation)
    # print(estimator.compute_rmse(pcd_target, pcd_model_trans, correspondence))
    #
    # # show aligned pointclouds
    # pcd_model.paint_uniform_color([1, 0.706, 0]) #yellow
    # pcd_target.paint_uniform_color([0, 0.651, 0.929]) #blue
    # o3d.visualization.draw_geometries([pcd_target, pcd_model])
    # print(np.sum(np.square(np.array(pcd_target.points) - np.array(pcd_model.points)), axis=1))