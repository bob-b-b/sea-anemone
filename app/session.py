import sys
sys.path.insert(0, 'C:/Users/au646858/OneDrive - Aarhus Universitet/Documents/_repositories/sea-anemone/app')

from panels import *
from typing import List
from pandas import DataFrame
import json_numpy
from anemone.forwards import Forward

from temframe import TEMframe

@nosj
class SessionSettings:
    map: MapSettings
    sounding: dbdtSoundingSettings
    table: TableSettings
    linked_settings: List[str] = None

import pandas as pd

@nosj
class Session:
    data:   TEMframe  = None
    models: DataFrame = None
    site:   DataFrame = None
    forwards: List[Forward] = None
    settings: SessionSettings = None
    save_dir: str = None

    def save(self, folder=None, binary_threshold=100):
        other = self.copy()
        if folder is None and other.save_dir is None:
            from os import makedirs
            makedirs('anemone_backup', exist_ok=True)
            folder = 'anemone_backup/'
            Warning('No folder specified for saving session, saving to default "anemone_backup/".')
        elif folder is None and other.save_dir is not None:
            folder = other.save_dir

        if other.data is not None:
            other.data.to_csv(folder+'data.csv', index=False)
            other.forwards = other.data.forward_operators
            other.data = 'data.csv'            
        if other.models is not None:
            other.models.to_csv(folder+'models.csv', index=False)
            other.models = 'models.csv'
        if other.site is not None:
            other.site.to_csv(folder+'site.csv', index=False)
            other.site = 'site.csv'                        

        if other.forwards is not None:
            for i in range(len(other.forwards)):
                other.forwards[i].save(folder + f'forward_{i}.json')
            other.forwards = [f'forward_{i}.json' for i in range(len(other.forwards))]

        other.__annotations__['data']   = str            
        other.__annotations__['models'] = str
        other.__annotations__['forwards'] = List[str]
        res = json_numpy.dumps(other._to_nosj(binary_threshold=binary_threshold), indent=4)
        with open(folder+'session.json', 'wt') as f:
            f.write(res)        

    def load_dataframes(self):
        fwd_list = []
        if self.forwards is not None and isinstance(self.forwards, list):
            for fwd_path in self.forwards:
                fwd = Forward.load(self.save_dir+fwd_path).logify()
                fwd_list.append(fwd)

        if self.data is not None and isinstance(self.data, str):
            self.data = TEMframe.from_pandas(pd.read_csv(self.save_dir+self.data), forward_operators=fwd_list)
            self.forwards = fwd_list
            self.data.forward_operators = fwd_list
            self.data.dmfwr = self.forwards[0]+self.forwards[1]
            self.data.dmfwr = self.data.dmfwr.logify()
        if self.models is not None and isinstance(self.models, str):
            self.models = pd.read_csv(self.save_dir+self.models)
        if self.site is not None and isinstance(self.site, str):
            self.site = pd.read_csv(self.save_dir+self.site)
        else:
            self.site = self.data.overview()

    @classmethod
    def from_folder(cls, folder):
        obj = cls.load(folder+'session.json')
        obj.load_dataframes()
        return obj

    @property
    def overview(self):
        if self.data is not None:
            return self.data.overview()
        else:
            return None