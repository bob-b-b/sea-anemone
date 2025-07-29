import re
import os
from dataclasses import dataclass
import numpy as np

def find_location_files(data_dir):
    data_dir = data_dir.replace('\\', '/')
    if not data_dir.endswith('/'):
        data_dir += '/'
    folders = [data_dir +  file for file in os.listdir(data_dir) if file.startswith('USF_Files_')]
    projects = [file.replace('USF_Files_', '').replace(data_dir, '')  for file in folders]
    locations_files = [folder + '/Notes_' + project + '.txt' for folder,project in zip(folders,projects)]
    return locations_files

def get_coordinates(fname):
    with open(fname, 'r') as file:
        content = file.read()

    pattern = re.compile(r'(\d+\.\d+)\s+(\d+\.\d+)')
    coordinates = pattern.findall(content)

    coordinates = [(float(lat), float(lon)) for lon, lat in coordinates]
    return coordinates

@dataclass
class Sweep:
    data: np.ndarray
    time: np.ndarray
    error: np.ndarray
    quality: np.ndarray
    tx_ramp: np.ndarray
    tx_ramp_time: np.ndarray
    current: float
    frequency: float
    is_noise: bool
    field_shift_factor: float
    time_delay: float
    ramp_time: float
    # rx_frontgate: float
    tx_turnontime: float
    ramp_time_on: float
    number: int
    channel: int
    low_pass: np.ndarray
    points: int
    
    @classmethod
    def from_usf_text(cls, txt):
        """parse a sweep block, will return the next sweep"""
        sweep = {}
        sweep_extra = {}
        lines = txt.lower().split('\n')
        i_head = lines.index('/end')
        for line in lines[:i_head]:
            i_colon = line.index(':')
            tmp = line[i_colon+1:]
            key = line[1:i_colon].replace('sweep_', '')
            
            cdict = sweep if key in cls.__dataclass_fields__ else sweep_extra
            if ',' in tmp:
                cdict[key] = np.array([float(x) for x in tmp.split(',')])
            else:
                try:
                    cdict[key] = float(tmp)
                except ValueError:
                    cdict[key] = tmp.strip()

        x = np.genfromtxt(lines[i_head+3:i_head+3+int(sweep['points'])], delimiter=',')#, dtype=(float,float,float,int))
        sweep['time'] = x[:, 0]
        sweep['data'] = x[:, 1]
        sweep['error']= x[:, 2]
        sweep['quality'] = x[:,3].astype(bool)
        tx_time = sweep['tx_ramp'][::2]*1
        tx_ramp = sweep['tx_ramp'][1::2]*1
        sweep['tx_ramp'] = tx_ramp
        sweep['tx_ramp_time'] = tx_time
        self = cls(**sweep)
        for key, value in sweep_extra.items():
            exec(f'self.{key} = value')
        return self
    
    @staticmethod
    def combine_sweeps(sweep_list):
        mega_sweep = {}
        mega_sweep_extra = {}
        for key in vars(sweep_list[0]):
            x = [eval(f'sweep.{key}') for sweep in sweep_list]
            try:
                x = np.array(x)
            except ValueError:
                x = np.array([str(xx) for xx in x])

            if key in Sweep.__dataclass_fields__:
                mega_sweep[key] = x
            else:
                mega_sweep_extra[key] = x
        csweep = Sweep(**mega_sweep)
        for key, value in mega_sweep_extra.items():
            exec(f'csweep.{key} = value')
        return csweep
    
    @classmethod
    def from_usf(cls, fname, combine=True):
        """parse a usf file, will return """
        with open(fname, 'r') as f:
            txt = f.read()
            header = txt[txt.index('/DATE:'):txt.index('/VOLTAGE_UNITS:')].replace('//END', '')
            sweeps = []
            count = 0
            while '/SWEEP_NUMBER' in txt:
                i = txt.index('/SWEEP_NUMBER:')
                sweeps.append(Sweep.from_usf_text(header+txt[i:]))
                txt = txt[i+1:]

        if combine:
            points = set([x.points for x in sweeps])
            mega_sweeps = []
            for pnts in points:
                mega_sweeps.append(cls.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
            return mega_sweeps
        else:
            return sweeps
    
    def flip_sign(self):
        self.data *= -1


    def get_polarity(self, gates=slice(4)):
        return np.sign(self.data[gates].mean())
    
    def correct_polarity(self, **kwargs):
        self.data *= self.get_polarity(**kwargs)        

    def save(self, fname):
        from pickle import dump
        with open(fname, 'wb') as outfile:
            dump(self, outfile)


    @classmethod
    def load(cls, fname, **kwargs):
        from pickle import load
        with open(fname, "rb") as a_file:
            data = load(a_file)
        return data

from anemone.forwards import Forward
from anemone.system import Loop, Receiver, Waveform, FilterChain, ButterworthFilter
from usf import Sweep
import numpy as np

def sweep2fwr(sweeps, fwr=Forward):
    points = set(swp.points for swp in sweeps)
    forwards = []
    for pnts in points:
        swp = next(swp for swp in sweeps if swp.points == pnts)
        tx = Loop.square(swp.loop_size[0])
        rx = Receiver(x=swp.coil_location[0], y=swp.coil_location[1])
        wv = Waveform(swp.tx_ramp_time, -swp.tx_ramp)
        filter_chain = []
        for f_cut, order in swp.low_pass[::2], swp.low_pass[1::2]:
            filter_chain.append(ButterworthFilter(f_cut))
        fc = FilterChain(filter_chain)
        time = swp.time
        forwards.append(fwr(tx, rx, time, wv, fc, tolerance=1e-6))
    return forwards

def sweep2dataframes(sweeps):
    import pandas as pd

    points = set([x.points for x in sweeps])

    mega_sweeps = []
    for pnts in points:
        mega_sweeps.append(Sweep.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
    lm,hm = mega_sweeps

    n_sites,n_gates = lm.data.shape

    lm.data  = np.pad(lm.data, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    lm.time  = np.pad(lm.time, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    lm.error = np.pad(lm.error, ((1,0), (0,0)), mode='constant', constant_values=np.nan)

    lm.date     = np.pad(lm.date, (1,0), mode='constant', constant_values=np.nan)
    lm.location = np.pad(lm.location, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    lm.daytime  = np.pad(lm.daytime, (1,0), mode='constant', constant_values=np.nan)

    data_avg = {
        'site_id': np.concatenate([np.ones(n_gates, dtype=int)*i for i in range(-1, n_sites)]),
        'dbdt': lm.data.flatten(),
        'error':   lm.error.flatten(),
        'inuse_auto': [True for _ in lm.data.flatten()],
        'inuse_manual': [np.nan for _ in lm.data.flatten()],
        'time': lm.time.flatten(),
        'gate_id': np.concatenate([np.arange(n_gates) for i in range(-1, n_sites)]),
        'system_id': ['lm' for _ in lm.data.flatten()],
        'date':     np.concatenate([np.ones(n_gates, dtype=int)*x for x in lm.date]),
        'latitude': np.concatenate([np.ones( n_gates, dtype=float)*x for x in lm.location[:, 1]]),
        'longitude':np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 0]]),
        'elevation':np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 2]]),
        'daytime':  np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.daytime]),
    }
    df_data = pd.DataFrame(data_avg)

    n_sites,n_gates = hm.data.shape
    
    n_sites,n_gates = hm.data.shape
    hm.data = np.pad(hm.data, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    hm.time = np.pad(hm.time, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    hm.error = np.pad(hm.error, ((1,0), (0,0)), mode='constant', constant_values=np.nan)

    hm.date = np.pad(hm.date, (1,0), mode='constant', constant_values=np.nan)
    hm.location = np.pad(hm.location, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
    hm.daytime = np.pad(hm.daytime, (1,0), mode='constant', constant_values=np.nan)

    data_avg = {
        'site_id': np.concatenate([np.ones(n_gates, dtype=int)*i for i in range(-1, n_sites)]),
        'dbdt': hm.data.flatten(),
        'error':   hm.error.flatten(),
        'inuse_auto': [True for _ in hm.data.flatten()],
        'inuse_manual': [np.nan for _ in hm.data.flatten()],
        'time': hm.time.flatten(),
        'gate_id': np.concatenate([np.arange(n_gates) for i in range(-1, n_sites)]),
        'system_id': ['hm' for _ in hm.data.flatten()],
        'date': np.concatenate([np.ones(n_gates, dtype=int)*x for x in lm.date]),
        'latitude': np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 1]]),
        'longitude': np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 0]]),
        'elevation': np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 2]]),
        'daytime': np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.daytime]),
    }
    df_data = pd.concat([df_data, pd.DataFrame(data_avg)], ignore_index=True)
    df_data = df_data.sort_values(by=['site_id','system_id', 'gate_id'])
    df_data = df_data.reset_index(drop=True)
    df_data.loc[df_data['time']>1e-3, 'inuse_auto'] = False

    df_data['error_lb'] = df_data['dbdt']-df_data['dbdt']/(1. + df_data['error']/100.)
    df_data['error_ub'] = df_data['dbdt']*(1. + df_data['error']/100.)-df_data['dbdt']

    df_data['log10_dbdt'] = np.log10(df_data['dbdt'])


    df_data['sys_gate'] = df_data['system_id'].astype(str) + '-' + df_data['gate_id'].astype(str)

    # Pivot the table: index by site_id and time, columns by sys_gate, values as dbdt
    pivot = df_data.pivot_table(
        index=['site_id'],
        columns='sys_gate',
        values='dbdt'
    )

    return pivot, df_data    

if __name__ == '__main__':
    data_folder = "O:/Nat-Tech_HGG-Projects/2025_sTEM_DollowSomalia/sTEM Profiler data/sTEM35/2025_0227"
    location_files = find_location_files(data_folder)
    # coordinates = get_coordinates(location_files[0])
    # print(coordinates)
    print(location_files)