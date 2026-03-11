from typing import List
from pandas import DataFrame
import json_numpy
from anemone.forwards import Forward
from temframe import TEMframe
from nosj import nosj
from basepanel import PanelSettings

from numpy import nan as np_nan

import pandas as pd
def rounded_nanmean(x):
    return round(x.mean(), 2)


@nosj
class Session:
    data:      TEMframe  = None
    models:    DataFrame = None
    site:      DataFrame = None
    lines:     DataFrame = None
    boreholes: DataFrame = None
    rock_map : dict      = None
    forwards:  List[Forward] = None
    settings:  List[PanelSettings] = None
    save_dir:  str = None
    dem_path:  str = None
    dem_name:  str = None

    def save(self, folder=None, binary_threshold=100):
        self.update_site_table()
        other = self.copy()
        
        if folder is None and other.save_dir is None:
            from os import makedirs
            makedirs('anemone_backup', exist_ok=True)
            folder = 'anemone_backup/'
            other.save_dir = 'anemone_backup/'
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
        if other.lines is not None:
            other.lines.to_csv(folder+'lines.csv', index=False)
            other.lines = 'lines.csv'
        if other.boreholes is not None:
            print("boreholes to dataframe here")
            other.boreholes.to_csv(folder+'boreholes.csv', index=False)
            other.boreholes = 'boreholes.csv'
        if other.rock_map is not None:
            # Convert dict {"Clay": "#hex"} to DataFrame for saving
            df_rock = pd.DataFrame(list(other.rock_map.items()), columns=['RockType', 'Color'])
            df_rock.to_csv(folder + 'rock_map.csv', index=False)
            other.rock_map = 'rock_map.csv'

        if other.forwards is not None:
            for i in range(len(other.forwards)):
                other.forwards[i].save(folder + f'forward_{i}.json')
            other.forwards = [f'forward_{i}.json' for i in range(len(other.forwards))]

        other.__annotations__['data']   = str            
        other.__annotations__['site']   = str            
        other.__annotations__['models'] = str
        other.__annotations__['lines']   = str
        other.__annotations__['boreholes'] = str
        other.__annotations__['rock_map'] = str            
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
        
        if self.models is not None and isinstance(self.models, str):
            self.models = pd.read_csv(self.save_dir+self.models)

        if self.site is not None and isinstance(self.site, str):
            self.site = pd.read_csv(self.save_dir+self.site)
        else:
            self.update_site_table()

        if self.boreholes is not None and isinstance(self.boreholes, str):
            df_flat = pd.read_csv(self.save_dir + self.boreholes)            
            from Sections_plotting import dataframe_to_boreholes
            self.borehole_list = dataframe_to_boreholes(df_flat)
            self.boreholes = df_flat
        if self.rock_map is not None and isinstance(self.rock_map, str):
            # This is the actual conversion step
            rock_df = pd.read_csv(self.save_dir + self.rock_map)
            self.rock_map = dict(zip(rock_df['RockType'], rock_df['Color']))

        if self.lines is not None and isinstance(self.lines, str):
            self.lines = pd.read_csv(self.save_dir+self.lines)

    @classmethod
    def from_folder(cls, folder):
        obj = cls.load(folder+'session.json')
        obj.load_dataframes()
        return obj

    @property
    def overview(self):
        if self.site is not None:
            return self.site
        self.update_site_table()
        return self.site        

    def update_site_table(self):
        if self.data is not None:
            df = self.data.copy()
            df['include'] = df['inuse_manual'].astype(bool, copy=True).fillna(df['inuse_auto'])
            aggfunc = dict(                        
                        date=('date','first'),
                        daytime=('daytime','first'),
                        latitude=('latitude','first'),
                        longitude=('longitude','first'),
                        elevation=('elevation','first'),
                        utm_x=('utm_x','first'),
                        utm_y=('utm_y','first'),
                        distance=('distance','first'),
                        )

            if 'misfit' in df.columns:
                aggfunc['misfit'] = ('misfit', rounded_nanmean)
                aggfunc['gates_used']=('include', 'sum')
                df.loc[df['include']==False, 'misfit'] = np_nan

            site = df.groupby('site_id', as_index=False).agg(**aggfunc)

            if self.models is not None:
                doi = self.models.groupby('site_id', as_index=False).agg(doi=('doi', 'first'))
                site = site.merge(doi, left_on='site_id', right_on='site_id')
            self.site=site