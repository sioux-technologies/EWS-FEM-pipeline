import copy
from pathlib import Path
import numpy as np
import pyvista as pv
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

def match_settings(skin: pv.PolyData):
    bounds = np.array(skin.bounds)
    settings = Settings()
    settings.model.geometry.radius_breast = float(np.abs((bounds[2] - bounds[3])))
    settings.model.geometry.radius_nipple = float(0.005)
    settings.model.mesh.order = 1
    settings.simulation.control_step2.time_steps = float(0)
    return settings

if __name__ == "__main__":
    # Import target surface and determine center (nipple)
    filepath = Path(r"C:\Users\stormf\OneDrive - Sioux Group B.V\Documents\EWS data\EWS_dataset\3031_01_lr.frame_001.obj")
    skin = load_obj_file(filepath, scale = 0.2) #data is not to scale, hence the 0.2 (guesstimated)

    # Translate such that the nipple is at the origin
    nipple_coord = point_clicker(skin, message='Click point for nipple. ')
    skin.translate(-1*nipple_coord[0], inplace=True)

    # Segment the breast and get projection points
    skin_segmented = extract_breast(skin)
    points, projected_real = generate_projection_points(skin_segmented)

    # Prepare settings and output files
    folder = Path(r"C:\Users\stormf\PycharmProjects\EWS-FEM-pipeline\optimization")
    filepath_out = Path(folder) / filepath.stem
    filepath_out_toml = filepath_out.with_suffix(f'.toml')

    # first guess for radius and write settings
    first_guess_settings = match_settings(skin)
    write_settings_to_toml(filepath = filepath_out_toml, settings = match_settings(skin_segmented))

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

    # compute initial RMSE and transformation
    correspondence = o3d.utility.Vector2iVector(np.repeat(np.where(np.sum(projected_real, axis=1) != np.nan), 2).reshape(-1, 2))
    estimator = o3d.pipelines.registration.TransformationEstimationPointToPoint()
    print(estimator.compute_rmse(pcd_target, pcd_model, correspondence))
    transformation = estimator.compute_transformation(pcd_model, pcd_target, correspondence)
    # Copy model cloud and transform
    pcd_model_trans = copy.deepcopy(pcd_model).transform(transformation)
    print(estimator.compute_rmse(pcd_target, pcd_model_trans, correspondence))

    # show aligned pointclouds
    pcd_model_trans.paint_uniform_color([1, 0.706, 0]) #yellow
    pcd_target.paint_uniform_color([0, 0.651, 0.929]) #blue
    o3d.visualization.draw_geometries([pcd_target, pcd_model_trans])

