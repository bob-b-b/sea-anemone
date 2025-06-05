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
    rx_frontgate: float
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
        lines = txt.lower().split('\n')
        i_head = lines.index('/end')
        for line in lines[:i_head]:
            i_colon = line.index(':')
            tmp = line[i_colon+1:]
            key = line[1:i_colon].replace('sweep_', '')
            if ',' in tmp:
                sweep[key] = np.array([float(x) for x in tmp.split(',')])
            else:
                sweep[key] = float(tmp)
        x = np.genfromtxt(lines[i_head+3:i_head+3+int(sweep['points'])], delimiter=',')#, dtype=(float,float,float,int))
        sweep['time'] = x[:, 0]
        sweep['data'] = x[:, 1]
        sweep['error']= x[:, 2]
        sweep['quality'] = x[:,3].astype(bool)
        tx_time = sweep['tx_ramp'][::2]*1
        tx_ramp = sweep['tx_ramp'][1::2]*1
        sweep['tx_ramp'] = tx_ramp
        sweep['tx_ramp_time'] = tx_time
        return cls(**sweep)
    
    @staticmethod
    def combine_sweeps(sweep_list):
        mega_sweep = {}
        for key in vars(sweep_list[0]):
            x = np.array([eval(f'sweep.{key}') for sweep in sweep_list])
            mega_sweep[key] = x
        return Sweep(**mega_sweep)
    
    @classmethod
    def from_usf(cls, fname):
        """parse a usf file, will return """
        with open(fname, 'r') as f:
            txt = f.read()
            sweeps = []
            count = 0
            while '/SWEEP_NUMBER' in txt:
                i = txt.index('/SWEEP_NUMBER:')
                sweeps.append(Sweep.from_usf_text(txt[i:]))
                txt = txt[i+1:]

        points = set([x.points for x in sweeps])
        mega_sweeps = []
        for pnts in points:
            mega_sweeps.append(cls.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
        return mega_sweeps
    
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
    

if __name__ == '__main__':
    data_folder = "C:/Users/au646858/Downloads/2025_0227"
    location_files = find_location_files(data_folder)
    # coordinates = get_coordinates(location_files[0])
    # print(coordinates)
    print(location_files)