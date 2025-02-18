# Detailed Settings 

---

## Table of Contents
1. [Model](#model)
    1. [Mesh](#mesh)
2. [Geometry](#geometry)
3. [Simulation](#simulation)
    1. [Control Step 2](#control_step2)
    2. [Time-stepper Step 2](#timestepper_step2)
    3. [Animation](#animation)

In this document we elaborate on the settings which are not directly necessary or relevant for the user to change, 
though we wish to list them here for completeness or for debug purposes. Most of these settings relate to solver settings
or detailed geometry/mesh settings which are sufficiently good by default. This document discusses the fields in the same
order as in the [all_default_settings.toml](/all_default_settings.toml). Only the settings in 
[adjustable_default_settings.toml](/adjustable_default_settings.toml) can be safely adjusted.

## 1. Model <a name="model"></a>
Again, within the `[model]` field, we can distinguish between the mesh and geometry subfields. These are discussed in their
respective subsections.

### 1.1 Mesh <a name="mesh"></a>
In the `[model.mesh]` field, two relevant, additional settings are present which gives the user more control over the mesh.
These settings should only ever be changed when a very coarse mesh is sought after. The two parameters are:

- `optimize: bool = true`: Option to optimize the mesh of the model using the default `gmsh` tetrahedral mesh optimizer, 
or the "HighOrder" optimizer for high order meshes (see input parameter `order`). Typically, the optimizer smoothens the
mesh allowing for a more consistent mesh generation.
- `order: int = 2`: Sets the order of the elements. Can only be 1 or 2. Order 1 implies tri3 en tet4 elements,
while order 2 implies tri6 and tet10 elements. See 
[surface elements](https://help.febio.org/docs/FEBioUser-4-7/UM47-3.6.2.2.html) and 
[solid elements](https://help.febio.org/docs/FEBioUser-4-7/UM47-3.6.2.1.html) for visualization. Though, one should be 
careful: The quality of first order meshes is far too inadequate for FEM simulation at this scale and the user is strongly
discouraged for genuine use.

### 1.2 Geometry <a name="geometry"></a>
Within the `[model.geometry]` fields, there is one setting that allows for change of the adipose rectangle, attached to
the back of the quarter circle (see the ReadMe image in  section 4.1.2):

- `thickness_chest_wall: float = 0.002 [meters]`: Sets the thickness of the rectangle attached to the chest, enclosed 
by the points `A`, `C`, `D` and `E`. When the 2D model is revolved, the rectangle transforms into a cylinder, which
is subject to the boundary conditions of the parabolic jump. In contrast to the other geometry parameters, 
`thickness_chest_wall` does not scale with the `radius`. In the figure, `thickness_chest_wall` corresponds with `d`. 
Typically, `thickness_chest_wall` does not need to be changed, as this a merely a FEM construction to apply the boundary
conditions, but one should stay within the range 0.0015 < `thickness_disk` < 0.005.

## 2. Simulation <a name="simulation"></a>
The entire FEBio simulation consists of two parts which run after each other. The first part concerns itself with the 
implementation of gravity, while the second part sets the parabolic jump. In the `all_default_settings.toml` file, 
the distinct settings are represented by the name of the settings field. All settings belonging to the gravity part have
a suffix `_step1`, while all settings of the jump part have a suffix `_step2`. Is it important to mention that these 
settings are related to the solver of the respective steps and not to the physical properties of - for example - the 
parabolic jump itself; these settings have a separate field. The extensive list of options can be found in the 
[FEBio documentation](https://help.febio.org/docs/FEBioUser-4-7/UM47-Section-3.3.html); in particular the subsections 
3.3.1 Control Parameters and 3.3.2 Time Stepper Parameters are relevant for this document. 

As mentioned, the entire simulation can be broken down in two sections which run after each other. The first section 
concerns the implementation of gravity which is a numerical, but otherwise unphysical, necessity. The settings for this
part are sufficient for the current implementation and do not require any fine-tuning. In theory, these settings are 
accessible for the user, with the field `[simulation.<...>_step1]`, though we strongly discourage to change them.

The second part represents the solver settings of the parabolic jump. The relevant fields here are 
`[simulation.control_step2]` and `[simulation.timestepper_step2]`, which we discuss in the follow-up subsections.

### 2.1 Control Step 2 <a name="control_step2"></a>
The field `[simulation.control_step2]` has two relevant settings which allow the user to change the total simulation 
duration of the parabolic jump:

- `time_steps: float = 120 [Dimensionless]`: Sets the number of time steps for the entire second part of the simulation,
i.e. the parabolic jump. 
- `step_size: float = 0.01 [seconds]`: Sets the time step size for the second part of the simulation.

The product of the two above-mentioned parameters determines the total simulation time of the parabolic jump, i.e.
`time_steps` x `step_size` = simulation time; which is by default set to 1.2 seconds. For small jumps, the physical time
in the air takes about 0.2 seconds. However, the breast continues to oscillate thereafter until it comes to a
full stop. The remaining second of the simulation is dedicated to this damped oscillation. Though, one can imagine that
larger jumps take longer, so it is up to the user to choose a reasonable value for `time_steps`. Typically, `time_steps`
should be in-between 100 and 150 (or 1 and 1.5 seconds for a fixed `step_size`).

Technically, the value for `step_size` also sets the time between two succeeding calculations. If this time step is too 
large, the solver may have difficulty with converging, especially with large mesh deformations such as in the beginning 
of the jump. FEBio has a built-in automatic time stepper, which can decrease the step size if the solver has trouble 
converging. The specifics of this automatic time stepper are discussed in the next section. Typically, it is not 
necessary to change `step_size` as this step size will strictly be overwritten by settings in the time-stepper. If you
wish to change the total simulation time, we recommend changing `time_steps` instead. If you wish to change the 
`step_size` because of convergence issues, we advise changing `dtmax` in `[simulation.animation]` instead and
leave `step_size` unaltered.

### 2.2 Time-stepper step 2 <a name="timestepper_step2"></a>
The field `[simulation.timestepper_steps2]` concerns with the automatic time stepper as mentioned in the previous subsection.
Relevant here is one settings:

- `max_retries: int = 20 [Dimensionless]`: Maximum number of times a time step is restarted.

FEBio makes use of an auto-time stepper. This auto-stepper will adjust the time step size depending on the convergence 
success of the prior time step. In practice this boils down to FEBio automatically decreasing the time step in case
one particular time step does not converge. 
`max_retries` sets an upper bound for the number of times a time step is restarted once it does not converge. One can set
this value a bit higher, though lower is discouraged due to risk of not converging at all; should the simulation not
converge with the given number of retries, then the simulation halts. We also encourage the user not to set to an extreme
high value, else we run into the risk of a never-ending simulation in the event of severe convergence issues. For more
information, we refer to the [FEBio documentation](https://help.febio.org/docs/FEBioUser-4-7/UM47-Subsection-3.3.2.html).

Counterintuitively, the `dtmax` field in `[simulation.timestepper_steps2]` in theory does affect the maximum time stepper,
but this is in turn overwritten by `dtmax` in `[simulation.animation]` (see next subsection). So the user should **not** adjust `dtmax` 
in `[simulation.timestepper_steps2]`

### 2.3 Animation <a name="animation"></a>
For the field `[simulation.animation]` there is one additional setting which is strongly tied with the automatic time
stepper from section 2.2. Here we explain an additional setting which is relevant for the solver:

- `dtmax: float = 0.01 [seconds]`: Sets the maximum time step size.

`dtmax` is a parameter that sets an upper bound for the maximum time step size, and helps constrain the range of possible time steps. This value overwrites the value for `step_size` in the Control field.
Currently, the default value is set to `0.01`, which is good for the current simulations. Though, we will mention that 
finding a better value may help speeding up the simulation. This remains a topic that belongs to the list of open issues.
Thus far, we found that increasing `dtmax` tends to also increase the simulation time.

Do **not** confuse `dtmax` in `[simulation.animation]` with  `dtmax` in `[simulation.timestepper_steps2]` - the latter is 
overwritten by the prior field.
