import tomllib

import numpy as np
from pydantic import (BaseModel,
                      Field)
from ews_fem_pipeline.prepare_simulation.simulation_settings import Settings
from limols import LimolsSettings
from pathlib import Path
from typing import Any, Dict

class LimolsUserInput(BaseModel):
    n_residuals: int = 200
    maxfev: int = 1000
    rhobeg: float = 0.1
    rhoend: float = 5e-8
    atol: float = 1e-8
    rtol: float = 0
    geom_fac: float = 1
    trust_region_method: str = "slsqp"
    p: int = 2


class FileSettings(BaseModel):
    target_mesh_filename: str = 'target_mesh_filename'
    output_folder: str = 'output_folder'
    preloaded_meshes_folder: str = 'preloaded_meshes_folder'

class RangeSettings(BaseModel):
    setting_name : str
    x0: float
    scale: float = 1
    xl: float = -np.inf
    xu: float = np.inf

    def return_information(self):
        return {'setting_name':self.setting_name,
                'x0':self.x0,
                'scale':self.scale,
                'xl':self.xl,
                'xu':self.xu,}

class OptimizationSettings(BaseModel):
    filesettings: FileSettings = FileSettings()
    limols: LimolsUserInput = LimolsUserInput()
    optimization_parameters: Dict[str, RangeSettings] = Field(
        default = RangeSettings(setting_name = 'radius_breast', x0 = 0.07, xl = 0.03, xu = 0.15))

    def get_limols_input_values(self):
        info_dict = {'setting_name':[],
                'x0':[],
                'scale':[],
                'xl':[],
                'xu':[]}
        for parameter in self.optimization_parameters.values():
            parameter_info = parameter.return_information()
            for key, value in parameter_info.items():
                info_dict[key].append(value)
        return info_dict

    def set_limols_settings(self) -> LimolsSettings:
        info_dict = self.get_limols_input_values()
        limols_settings = LimolsSettings(**info_dict)
        for field in LimolsUserInput.model_fields:
            setattr(limols_settings, field, getattr(self.limols, field))
        return limols_settings

    def get_model_parameters(self):
        setting_names = []
        for parameter in self.optimization_parameters.values():
            setting_names.append(parameter.setting_name)
        return setting_names



def load_optimization_settings_toml(filepath: Path):
    assert filepath.suffix == ".toml", "The input file does not have the correct file extension. Must be .toml"
    with open(filepath, 'rb') as f:
        data = tomllib.load(f)
    return OptimizationSettings.model_validate(data)
