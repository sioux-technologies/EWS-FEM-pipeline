################################################################################################
# The following script should be opened within the Blender python API. That is the 'scripting' #
# section in the top ribbon. Make sure that the paths are set up correctly, by changing the    #
# input for "filepath".                                                                        #
################################################################################################

from pathlib import Path

import bpy
import numpy as np

#  Assign the path to the single .feb file you wish to load in.
filepath = Path(...)


if __name__ == "__main__":

    filepath = Path(filepath)

    assert filepath.suffix == ".feb", "The input file does not have the correct file extension. Must be .feb"

    # Get name of input file
    filename = filepath.stem

    print(filename)

    # Output directory
    filepath_output = filepath.parent / "output"

    # Define paths output .obj file for surface mesh and output .npy file for displacements
    filepath_obj = (filepath_output / filename).with_suffix(".obj")
    filepath_npy = (filepath_output / filename).with_suffix(".npy")

    # Select all objects and delete them to start clean slate
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()

    # Load displacements file
    displacements = np.load(str(filepath_npy))

    # Read number of time steps
    n_frames = np.shape(displacements)[0]
    bpy.context.scene.frame_end = n_frames

    # Import obj file as bpy object and assign as active
    bpy.ops.wm.obj_import(filepath=str(filepath_obj))
    obj = bpy.context.active_object

    # Check if object is a mesh object
    assert obj.type == 'MESH', "Object is not a MESH!"

    # Get vertex positions from object
    pos_vert = np.array([v.co for v in obj.data.vertices])

    # Initialize displaced positions
    disp = np.zeros_like(pos_vert)
    disp_data = []

    # Calculate absolute displaced positions w.r.t each vertex
    for i in range(n_frames):
        disp = pos_vert + displacements[i]
        disp_data.append(disp.copy())

    # Assign keyframe to each frame
    # Assign new vertex positions per frame
    for i_frame in range(n_frames):
        block = obj.shape_key_add(name=str(i_frame), from_mix=False)  # returns a key_blocks member
        block.value = 1.0
        block.mute = True
        for (vert, co) in zip(block.data, disp_data[i_frame], strict=True):
            vert.co = co

        # keyframe off on frame zero
        block.mute = True
        block.keyframe_insert(data_path='mute', frame=0, index=-1)

        block.mute = False
        block.keyframe_insert(data_path='mute', frame=i_frame + 1, index=-1)

        block.mute = True
        block.keyframe_insert(data_path='mute', frame=i_frame + 2, index=-1)
