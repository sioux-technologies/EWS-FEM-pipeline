# Optimization instruction
In this document we explain how the optimization works and how the optimization settings file should be written.
The optimization can be run by `fem-pipeline optimize optimization_settings_file.toml`
### Target mesh
The optimization tries to minimize the distance between model output and a given target mesh. The target mesh should be of the .obj file type, and the surface should include the full breast surface, but minor gaps are allowed and can be dealt with. 
The mesh can contain more than just the breast, as the first step in the optimization pipeline is to segment only the breast. 

### Optimization algorithm
The optimization uses derivative-free optimizer LIMOLS. This requires a residual input consisting of a fixed number of residuals which can be both positive or negative. 
In this optimization the residuals are the x-, y- and z- differences between points on the model surface and their closest neighbor on the target surface as found by scipy's KDTree function.
LIMOLS will iteratively try new parameter sets, where a model breast is generated using the FEM pipeline. The resulting geometry is then used to compute the residuals.

## Settings file
The settings file consists of three parts: file settings, LIMOLS settings and optimization parameters.

### File settings
The file starts with the `[filesettings]` section. The first file setting `target_mesh_filename` is the name of the .obj file containing the target mesh. 
Note: the target mesh file shoudl be in the same folder as the optimization settings file!

Optionally, the setting `output_folder` can be set with a string. This will create a subfolder containing the optimization output folders and files
If this setting is set to `None`, the output will be written to the current folder. 

### LIMOLS settings
In this section, settings for LIMOLS can be set. The most important ones are discussed, for the rest the LIMOLS documentation can be consulted.

`maxfev` sets the maximum number of iterations of the optimization. 
`rhoend` specifies the size of the trust region required to end the optimization before `maxfev` is reached
`p` is the number of parameters to be optimized in the optimization

### Optimization parameters

A variable number of parameters can be set to be optimized in the settings file. 
The parameters should each be set with a tag `[optimization_parameters.X]` where X can be any unique tag (e.g. 1, 2, 3, etc.).
The actual parameter name can be set with `setting_name`, which should be the full parameter name as used in the FEM pipeline. 
E.g. the parameter radius_breast can be set as `setting_name = "model.geometry.radius_breast"`.  

For each parameter should be set at least `x0` (initial guess) and `scale`. Scale specifies the scale of the parameter, which determines the size of the steps LIMOLS takes. 
The first step will be 0.1*scale, so choose wisely. 
Additionally, upper and lower bounds `xl` and `xu` can be set. 

## Output
The optimization will always create a folder with the same name as the target mesh file, `\target_mesh_file` or `\output_folder\target_mesh_file` if output_folder is specified.
In this folder all output from the FEM pipeline will be written (log files, .feb files, .obj files). 

All output files will be named after the used parameters multiplied by 1000. E.g. a simulation with optimized parameters radius_breast and angle_nipple with parameter values 0.07 and 22.5 will have output named 70_2250.obj.

Currently, no log file for the optimization is written.


## Tips and tricks
### 'Defaults' folder
Since the optimization always takes the same first steps if the parameters, x0 and scale is kept equal, the process can be sped up by using existing FEM output.
The model mesh for the default steps can be put in a folder `\defaults` in the parent folder. The optimization checks if there is a mesh with the right parameters in the defaults folder before generating a new mesh with the FEM pipeline.



