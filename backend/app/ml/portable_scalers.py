"""Numerical StandardScaler parameters, independent of sklearn pickle versions."""
from pathlib import Path
import json
import numpy as np
import joblib

class PortableStandardScaler:
    def __init__(self, parameters):
        self.mean_=np.asarray(parameters['mean'],dtype=np.float64) if parameters['mean'] is not None else None
        self.scale_=np.asarray(parameters['scale'],dtype=np.float64) if parameters['scale'] is not None else None
        self.with_mean=parameters['with_mean'];self.with_std=parameters['with_std']
        self.n_features_in_=parameters['features']

    def _array(self, values):
        data=np.asarray(values)
        data=np.array(data,dtype=data.dtype if data.dtype.kind=='f' else np.float64,copy=True)
        if data.ndim!=2 or data.shape[1]!=self.n_features_in_:
            raise ValueError('Scaler input feature count does not match its exported schema')
        return data

    def transform(self, values):
        data=self._array(values)
        if self.with_mean:data-=self.mean_.astype(data.dtype)
        if self.with_std:data/=self.scale_.astype(data.dtype)
        return data

    def inverse_transform(self, values):
        data=self._array(values)
        if self.with_std:data*=self.scale_.astype(data.dtype)
        if self.with_mean:data+=self.mean_.astype(data.dtype)
        return data

def load_scalers(path: Path):
    portable=path.with_suffix('.json')
    if portable.is_file() and (not path.exists() or portable.stat().st_mtime>=path.stat().st_mtime):
        payload=json.loads(portable.read_text(encoding='utf-8'))
        if payload.get('format')!='pengzhi-standard-scaler-v1':raise ValueError('Unknown scaler format')
        return {name:PortableStandardScaler(data) for name,data in payload['scalers'].items()}
    return joblib.load(path)
