# Open issues

---
The list below summarizes the open issues which ought to be addressed in a follow-up project. These are split into
(priority) model improvements and others.

## 1. Model improvements (priority)
- **Mesh self-check**. For certain breast geometries in combination with mesh settings, `gmsh` fails to construct a 
correct mesh. In particular, `gmsh` warns the user about so-called *inverse elements with negative jacobians*. These are
elements in which the node order is incorrect, causing a faulty element. Although `gmsh` outputs a warning, the rest of 
the code is ignorant about the faulty mesh and will continue to run until it attempts to run the  FEBio simulation, 
where it will raise an error. Currently, this is overcome by manually choosing a slightly different mesh `density` and 
retry the mesh generation until it succeeds. Preferably, this would be done automatically by the code without human 
intervention. Some attempts have been made to implement such a framework, but without success. For future work, one can
look into `gmsh` functions that calculate the jacobians of all elements in the mesh and check for negative values. `gmsh`
[functions](https://gitlab.onelab.info/gmsh/gmsh/blob/gmsh_4_13_1/api/gmsh.py) that could be helpful here are 
`getElementQualities` and `getJacobians`, which are used in `gmsh` 
[tutorial x6](https://gitlab.onelab.info/gmsh/gmsh/blob/gmsh_4_13_1/tutorials/python/x6.py).
- **The position of the nipple.** The mesh knows a cylindrical symmetry along the long axis which comes from revolving 
around that same axis. The position of the nipple is currently centered with the rotation axis, so that its position is 
strictly fixed. Adjusting the position would imply more geometry options, but adopting a different mesh generation scheme
which is less reliable on symmetry.
- **Asymmetry of the breast**. Naturally, a more realistic breast possesses some form of asymmetry for being it the left
or right breast. This would also imply a breaking of cylindrical symmetry like the prior bullet. One can for example 
define a parameter which sets the degree of symmetry, with being symmetrical and being fully asymmetrical.
- **Amorphously shaped tumors**. Currently, the tumors implemented in the model are represented by spheres
with a predetermined position and radius. In the model, this is accommodated by a Heaviside function, which effectively
replaces the material properties of the apparent tissue with those of the tumor. As an open issue, we are interested in 
more amorphously shaped tumors, which are not bound by spheres. Naturally, the mesh needs to be locally dense enough 
to accommodate more intricate features. One can also think about locally changing the mesh so that it can accommodate 
the tumor better.
- **Birthmarks/moles/skin roughness.** Realistically, skin is not perfectly smooth or monochrome but covered with 
birthmarks and moles. This has negligible effects on the mechanical properties of the breast but may play an important 
role in the detection of skin anomalies related to cancer. The cameras in the experimental set-up ought to be trained 
to detect such features, therefore implementing surface properties in the simulation is a useful addition to the pipeline. 
Evidently, such features should be added in the Blender environment where object rendering is central.

## 2. Miscellaneous (low priority)
- **Speed-up**. The FEM simulation, as presented in this pipeline, is to no extent considered optimized, in the sense that runs as 
fast as that it theoretically could. For this, we have done limited work on changing certain solver settings, but could not
find any drastic improvements. Here we provide some general remarks:
Increasing the mesh density naturally increases the total run time, but are also more susceptible towards time step
fails, e.g. due to a negative jacobian. This adds another factor for increasing simulation duration. Additionally, we
found that meshes with similar density do not necessarily finish simulating in similar times. There appears to be a 
large spread in duration which yields inconsistent success rates. Up to now, we cannot provide an explanation for this.
One of the simulation settings that we investigated, is the `dtmax` in `[simulation.animation]` which sets an upper bound
for the time steps in the FEBio automatic time stepper. By default, it is set to 0.01. We noticed that during the
latter part of the simulation, the breast model hardly deforms, at which FEBio automatically increases the time step.
Motivated by this, we increased the `dtmax` to 0.025 = 1/40 (fps) so that this latter part runs faster. However, we found
that larger time steps have an increased chance in time steps fails. In fact, we noticed an increase of 20% run time when we
increased `dtmax` from 0.01 to 0.025. Therefore, it strongly discouraged to increase the default `dtmax`. Potentially,
smaller values could very well decrease the run time, but this remains an open issue.
- **Consulting breast cancer experts.** It was advised to discuss any biomedical related issues we run into with 
oncologists. Though, this should be done whenever we have prepared enough questions worth asking, due to limited time 
availability.
- **Back surface mesh**. The back of the breast contains a mesh with distinct elements which are strictly unnecessary 
after the simulation has finished. This is because this part of the breast does not deform during the motion – this 
is a set boundary condition in the simulation. Removing these elements would in theory alleviate file memory, but it is
unknown how much this would contribute. At the same time, it is not trivial to determine which nodes should be discarded.
We mention it here as an open issue, though we admit this has low priority, unless memory load becomes significant.
- **Disk mesh back of breast/breast protrudes chest.** For the boundary conditions, a disk of adipose tissue is 
attached to the back of the breast. The back surface of this disk remains unperturbed throughout the simulation. During
the simulation though, a small but non-zero fraction of the breast ends up behind the disk,which is as if the breast 
protrudes the chest. The latter is of course not physical, but the effect is very limited. Like the previous bullet, we
present it here as an open issue, but also acknowledge it as low priority.