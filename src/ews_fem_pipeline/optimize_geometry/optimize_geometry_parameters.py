from pathlib import Path

from limols import LimolsSolver
import logging
import pyvista as pv
from pyvista import PolyData

from ews_fem_pipeline.optimize_geometry.load_data import load_obj_file, point_clicker
from ews_fem_pipeline.prepare_simulation import write_settings_to_toml, load_settings_from_toml
from ews_fem_pipeline.convert_simulation.feb_to_3d import feb_to_3d
from ews_fem_pipeline.optimize_geometry.optimization_settings import *
from scipy.spatial import KDTree as scikdtree

logger = logging.getLogger(__name__)

def optimize_geometry_parameters(toml_filepath: Path):

    assert toml_filepath.suffix == '.toml', "Optimization settings file must be .toml"

    optimization_settings = load_optimization_settings_toml(toml_filepath)
    parameter_locations = optimization_settings.get_model_parameters()

    # Prepare settings and output files
    target_path = Path(toml_filepath.parent / optimization_settings.filesettings.target_mesh_filename)
    title = target_path.stem
    if optimization_settings.filesettings.output_folder == 'none':
        output_folder = target_path.parent
    else:
        output_folder = target_path.parent / optimization_settings.filesettings.output_folder

    # Prepare input data
    skin_segmented = prepare_data(target_path)

    # Extract and set LIMOLS settings and solver
    settings_limols = optimization_settings.set_limols_settings()
    settings_limols.n_residuals = 200 * 3  # 200 projection points in 3 dimensions
    solver = LimolsSolver(settings_limols)

    # Get and run initial step
    parameter, expected_residual, step_size = solver.get_initial_step()
    residual, model_obj = breast_analysis(parameter_locations, parameter, output_folder, title, skin_segmented)
    parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)

    # 2nd to last step
    while not solver.done:
        residual, model_obj = breast_analysis(parameter_locations, parameter, output_folder, title, skin_segmented)
        parameter, expected_residual, step_size = solver.step(parameter, expected_residual, step_size, residual)

    save_final_images(model_obj, output_folder, skin_segmented, title)
    pass


def save_final_images(model_obj: Path, output_folder: Path, skin_segmented: PolyData, title: str):
    skin_segmented.save((output_folder / title / (title + '_segmented')).with_suffix(".obj"))

    plotter = pv.Plotter(off_screen=True)
    plotter.add_mesh(skin_segmented, color='blue', opacity=0.5)
    model_skin_final = pv.read(model_obj)
    center_breast(model_skin_final, nipple_coord=model_skin_final.points[np.argmax(model_skin_final.points[:, 1])])
    plotter.add_mesh(model_skin_final, color='yellow', opacity=0.5)
    plotter.view_xz(negative=True)
    plotter.screenshot((output_folder / title / 'result_front').with_suffix(".png"), transparent_background=True)
    plotter.view_yz()
    plotter.screenshot((output_folder / title / 'result_side').with_suffix(".png"), transparent_background=True)


def extract_breast(skin: pv.PolyData | pv.UnstructuredGrid) -> pv.PolyData:
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

def generate_projection_points(model_skin: pv.PolyData, n_points=10, n_slices = 10) -> np.ndarray:
    points = np.empty((0, 2))
    for phi in np.linspace(-1 / 2 * np.pi, 1 / 2 * np.pi, n_slices, endpoint=False):
        intsect = model_skin.slice(origin=(0, 0, 0), normal=(np.cos(phi), 0, np.sin(phi)))
        ends = intsect.points[[np.argmax(intsect.points[:, 2]), np.argmin(intsect.points[:, 2])]]
        lens = np.sqrt(ends[:, 0] ** 2 + ends[:, 2] ** 2)
        ws = np.concatenate((np.linspace(0.01, lens[1], n_points, endpoint=False),
                             -1 * np.linspace(0.01, lens[0], n_points, endpoint=False)))
        points = np.append(points, np.outer(ws, np.array([np.sin(phi), -1*np.cos(phi)])), axis=0)
    return points

def project_front(surface: pv.PolyData, points: np.ndarray) -> np.ndarray:
    """Finds the intersection between the lines given by projecting the projection points in the y-direction and the
    surface"""
    intercepts = []
    for point in points:
        projection_point = surface.ray_trace([point[0], 1, point[1]], [point[0], -1, point[1]], first_point=True)[0]
        if len(projection_point) > 0:
            intercepts.append(projection_point)
        else:
            intercepts.append([point[0], np.nan, point[1]])
            pass
    return np.array(intercepts)

def write_settings(parameter_locations, params, filepath_out_toml, settings_file: Path = None):
    if settings_file:
        #load alternate settings
        settings = load_settings_from_toml(settings_file)
    else:
        # use default settings
        settings = Settings()
    #set fixed settings for this problem
    settings.material.tumor.tumorous = False
    settings.simulation.control_step2.time_steps = float(0) #no dynamic steps
    # set values for given parameters
    for location, value in zip(parameter_locations, params):
        obj = settings
        steps = location.split('.')
        for attr in steps[:-1]:
            obj = getattr(obj, attr)
        setattr(obj, steps[-1], float(value))

    # Write to file
    write_settings_to_toml(filepath=filepath_out_toml, settings=settings)

def breast_analysis(parameter_locations: dict, parameter: np.ndarray, folder: Path, title: str, skin: pv.PolyData):
    # Run FEM model with given input parameters
    breast_model_obj = run_breast_model(parameter_locations, parameter, folder, title)
    # Load resulting model surface
    breast_surface = load_obj_file(breast_model_obj, switch_axes=False)
    # Calculate distance between model and target surfaces
    residuals = compare_geometries(breast_surface, skin)
    return residuals, breast_model_obj

def run_breast_model(parameter_locations: dict, params: np.ndarray, folder: Path, title: str) -> Path:
    output_title = '-'.join(f'{1000*param:.0f}' for param in params)
    if (Path(folder/'defaults'/output_title).with_suffix('.obj')).is_file():
        obj_files = Path(folder/'defaults'/output_title).with_suffix('.obj')
    else:
        from ews_fem_pipeline.cli import generate, fem #circumvent circular import
        # Write parameters to settings file
        filepath_out_toml = (folder/title/output_title).with_suffix('.toml')
        write_settings(parameter_locations, params, filepath_out_toml)

        # Generate mesh, run, and generate displaced mesh .obj file
        mesh_files = generate.callback([filepath_out_toml])
        feb_files = fem.callback(mesh_files, jobs=0)
        if len(feb_files)<1:raise Exception('FEBio did not return result, terminating optimization')
        obj_files = feb_to_3d(feb_files[0], remove_chest=True)

    return obj_files

def compare_geometries(breast_model_geom: pv.PolyData|pv.UnstructuredGrid, breast_target_geom: pv.PolyData,
                       n_points: int =10, n_slices: int = 10) -> np.ndarray:
    # Load model mesh
    center_breast(breast_model_geom, nipple_coord = breast_model_geom.points[np.argmax(breast_model_geom.points[:, 1])])
    #Project projection points on model mesh
    breast_model_geom= breast_model_geom.extract_surface(algorithm=None)
    projection_points = generate_projection_points(breast_model_geom, n_points, n_slices)
    projected_model = project_front(breast_model_geom, projection_points)

    dists, inds = closest_points(breast_target_geom, projected_model)
    dx = (breast_target_geom.points[inds] - projected_model).flatten()
    return dx

def closest_points(poly: pv.PolyData, points: np.ndarray):
    tree = scikdtree(poly.points)
    distances, indices = tree.query(points)
    return distances, indices

def show_results(filepath_model_obj: Path, skin_segmented: pv.PolyData):
    model_skin_final = (load_obj_file(filepath_model_obj))
    center_breast(model_skin_final, nipple_coord=model_skin_final.points[np.argmax(model_skin_final.points[:, 1])])

    plotter = pv.Plotter()
    plotter.add_axes()
    plotter.view_xz()
    plotter.add_mesh(model_skin_final, opacity=0.8, color='yellow')
    plotter.add_mesh(skin_segmented, opacity=0.8, color='blue')
    plotter.show()

def prepare_data(filepath) -> pv.PolyData:
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
        # If no nipple is given, let user define nipple coordinate through interface
        nipple_coord = point_clicker(skin, message='Click point for nipple. ')[0]

    # Translate such that nipple is at origin
    skin.translate(-1 * nipple_coord, inplace=True)
    # Find direction of nipple
    nipple_normal = find_area_normal(skin, radius = 0.02, center=(0,0,0))
    # Turn mesh such that nipple direction is in YZ plane
    nipple_normal[2] = 0
    nipple_normal = nipple_normal/np.linalg.norm(nipple_normal)
    rot_axis = np.cross(nipple_normal, (0, 1, 0))
    rot_axis = rot_axis / np.linalg.norm(rot_axis)
    rot_angle = np.degrees(np.arccos(np.dot(nipple_normal, (0, 1, 0))))
    skin.rotate_vector(vector=rot_axis, angle=rot_angle, inplace=True)


def find_area_normal(surface: pv.PolyData | pv.UnstructuredGrid, radius: float, center: tuple = (0, 0, 0)) -> np.ndarray:
    search_volume = pv.Sphere(radius=radius, center=center)
    search_area = surface.select_interior_points(search_volume, inside_out=False)
    search_area = search_area.threshold(0.5)
    search_area = search_area.extract_surface(algorithm=None)
    nipple_normal = np.average(search_area.compute_normals()['Normals'], axis=0)
    nipple_normal = nipple_normal / np.linalg.norm(nipple_normal)
    return nipple_normal

