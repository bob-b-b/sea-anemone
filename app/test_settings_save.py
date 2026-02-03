import sys
sys.path.insert(0, 'C:/Users/au646858/OneDrive - Aarhus Universitet/Documents/_repositories/sea-anemone/app')

from panels import *
from typing import List
from pandas import DataFrame
import json_numpy

@nosj
class SessionSettings:
    map: MapSettings
    sounding: dbdtSoundingSettings
    table: TableSettings
    linked_settings: List[str] = None

import pandas as pd

@nosj
class Session:
    data:   DataFrame = None
    models: DataFrame = None
    settings: SessionSettings = None

    def save(self, filename, binary_threshold=100):
        if self.data is not None:
            self.data.to_csv(f'{filename.split(".")[0]}_data.csv', index=False)
            self.data = f'{filename.split(".")[0]}_data.csv'
            
        if self.models is not None:
            self.models.to_csv(f'{filename.split(".")[0]}_models.csv', index=False)
            self.models = f'{filename.split(".")[0]}_models.csv'
        self.__annotations__['data']   = str            
        self.__annotations__['models'] = str
        res = json_numpy.dumps(self._to_nosj(binary_threshold=binary_threshold), indent=4)
        with open(filename, 'wt') as f:
            f.write(res)

    # def load(filename):
    def load_dataframes(self):
        if self.data is not None and isinstance(self.data, str):
            self.data = pd.read_csv(self.data)
        if self.models is not None and isinstance(self.models, str):
            self.models = pd.read_csv(self.models)





if __name__ == "__main__":
    
    map_settings = MapSettings(id='map')
    sounding_settings = dbdtSoundingSettings(id='sounding')
    table_settings = TableSettings(id='table')

    settings = SessionSettings(
        map=map_settings,
        sounding=sounding_settings,
        table=table_settings
    )
    session=Session(
        data = pd.read_csv('C:/Users/au646858/OneDrive - Aarhus Universitet/Documents/_repositories/sea-anemone/data.csv'),
        models = None,
        settings = settings
    )
    print('ready to save')
    session2 = Session.load('session1.json')
    session2.load_dataframes()
    print(session2.data)