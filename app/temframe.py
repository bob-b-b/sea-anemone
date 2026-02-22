from pandas import DataFrame
import pandas as pd
import numpy as np
import usf
import inspect
from contextlib import contextmanager
import torch
import os

def silence(s):
    pass

from anemone.inversion import LogResistivity
from anemone.inversion import fastJac, SCI

iteration_cap = 10
if iteration_cap<50:
    import warnings
    warnings.warn("The default iteration cap for TEMframe inversion has been reduced to 10 to speed up testing. Change it back to 50 for production runs.", UserWarning)


def make_log():
    """Initialize a log file by creating it empty or clearing if it exists."""
    try:
        with open('inversion_log.txt', 'w') as f:
            f.write('')
    except IOError as e:
        print(f"Error creating log file: {e}")
    

def write_log(message):
    print(message)
    with open('inversion_log.txt', 'a') as f:
        f.write(message+'\n')
    

class TEMframe(DataFrame):
    forward_operators = []
    history = []
    track_history = True

    def __init__(self, *args, **kwargs):
        if 'forward_operators' in kwargs:
            self.forward_operators = kwargs.pop('forward_operators')
        if 'history' in kwargs:
            self.history = kwargs.pop('history')
        if 'track_history' in kwargs:
            self.track_history = kwargs.pop('track_history')
        super().__init__(*args, **kwargs)
        # self.__post_init__()

    def overview(self):
        current_history = self.history.copy()

        df = self.pivot_table(
            index=['site_id'],
            values=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'],
            aggfunc='first'
        )
        # df['site_id'] = df.index
        if 'misfit' in self.columns:
            df['misfit'] = self.groupby('site_id')['misfit'].mean()

        # with self._skip_tracking():
        #     res = TEMframe(df, history=current_history.copy())
        # res.track_history = self.track_history
        # res._record_op()
        self.history = current_history
        return df

    @classmethod
    def from_usfzip(cls, zip_path, track_history=True):
        with open(zip_path, 'rb') as f:
            zip_bytes = f.read()
        return cls.from_zip_content(zip_bytes, track_history=track_history)
    
    @classmethod
    def from_zip_content(cls, zip_content, track_history=True):
        import zipfile
        import io
        import base64

        if isinstance(zip_content, str):
            zip_bytes = base64.b64decode(zip_content)
        else:
            zip_bytes = zip_content

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            usf_files = [x for x in z.namelist() if x.endswith('.usf')]
            sweeps = []
            for i, fname in enumerate(usf_files):
                with z.open(fname, 'r') as f:
                    new_sweeps = usf.Sweep.from_buffer(f, combine=False)
                    if set([x.points for x in new_sweeps]) == {6,22}:
                        sweeps += new_sweeps
                    else:
                        print(f'Ignoring {fname} because it does not contain both low and high moment data.')                    
            return cls.from_sweeps(sweeps, track_history=track_history, folder_path=z.namelist()[0]+'.zip')

    # @classmethod
    # def from_session(cls, session_zip):
    #     import zipfile
    #     import io
    #     import base64

    #     df_data = None
    #     df_overview = None
    #     df_models = None

    #     if isinstance(session_zip, str) and session_zip.endswith('.zip'):
    #         with open(session_zip, 'rb') as f:
    #             zip_bytes = f.read()
    #     elif isinstance(session_zip, str):
    #         zip_bytes = base64.b64decode(session_zip)
    #     else:
    #         zip_bytes = session_zip

    #     with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            
    #         with z.open('tem_data.csv', 'r') as f:
    #             df = pd.read_csv(f)
    #         with z.open('history.py', 'r') as f:
    #             history = f.readlines()
    #         history = [line.strip().decode('utf-8') for line in history]
            
    #         saved_forwards = [x for x in z.namelist() if x.endswith('.em1')]
    #         forward_operators = None
    #         if len(saved_forwards) > 0:
    #             from anemone.forwards import Forward, logify_forward
    #             lg_FWR = logify_forward(Forward)
    #             forward_operators = []
    #             for i in range(len(saved_forwards)):
    #                 with z.open(saved_forwards[i], 'r') as f:
    #                     fwr = lg_FWR.load(f)
    #                     fwr.tolerance=1e-6
    #                     forward_operators.append(fwr)
    #         df_data = cls.from_pandas(df, history=history, forward_operators=forward_operators)
    #         df_overview = df_data.overview()
    #         if 'models.csv' in z.namelist():
    #             with z.open('models.csv', 'r') as f:
    #                 df_models = pd.read_csv(f)
    #                 df_models = cls.from_pandas(df_models, history=history, forward_operators=forward_operators)
    #     return {'data': df_data, 'models': df_models, 'overview':df_overview}

    @classmethod
    def from_usf_folder(cls, folder_path, track_history=True):
        sweeps = []
        usf_files = [folder_path+f for f in os.listdir(folder_path) if f.endswith('.usf')]
        for usf_file in usf_files:        
            with open(usf_file, 'rb') as f:
                new_sweeps = usf.Sweep.from_buffer(f, combine=False)
                # if set([x.points for x in new_sweeps]) == {6,22}:
                if set([x.points for x in new_sweeps]) == {6,22} or set([x.points for x in new_sweeps]) == {20,27}:
                    sweeps += new_sweeps
                else:
                    print(f'Ignoring {usf_file} because it does not contain both low and high moment data.')
        return cls.from_sweeps(sweeps, track_history=track_history, folder_path=folder_path)

    @classmethod
    def from_sweeps(cls, sweeps, track_history=True, folder_path=None):
        # points = set([x.points for x in sweeps])
        # mega_sweeps = []
        # for pnts in points:
        #     mega_sweeps.append(usf.Sweep.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
        # try:
        #     lm,hm = mega_sweeps
        # except:
        #     print(len(mega_sweeps))
        #     print(points)
        #     print(folder_path)
        points = sorted(set([x.points for x in sweeps]))
        mega_sweeps = []
        print(f'Found sweeps with points: {points}')
        for pnts in points:
            mega_sweeps.append(usf.Sweep.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
       
        mega_sweeps = sorted(mega_sweeps, key=lambda swp: np.nanmin(swp.time))
        try:
            lm,hm = mega_sweeps
        except:
            print(len(mega_sweeps))
            print(points)
            print(folder_path)

        n_sites,n_gates = lm.data.shape
        n_gates += 1
        day_sort = np.argsort(lm.daytime)
        site_id = np.zeros(n_sites, dtype=int)
        site_id[day_sort] = np.arange(len(lm.daytime))
        site_id = np.insert(site_id, 0, -1)  # insert a dummy site_id for the loop

        lm.data  = np.pad(lm.data, ((1,0), (1,0)), mode='constant', constant_values=np.nan)
        lm.time  = np.pad(lm.time, ((1,0), (1,0)), mode='constant', constant_values=np.nan)
        lm.error = np.pad(lm.error, ((1,0), (1,0)), mode='constant', constant_values=np.nan)

        lm.date     = np.pad(lm.date, (1,0), mode='constant', constant_values=np.nan)
        lm.location = np.pad(lm.location, ((1,0), (0,0)), mode='constant', constant_values=np.nan)
        lm.daytime  = np.pad(lm.daytime, (1,0), mode='constant', constant_values=np.nan)


        data_avg = {
            'site_id': np.concatenate([np.ones(n_gates, dtype=int)*i for i in site_id]),
            'dbdt': lm.data.flatten(),
            'error':   lm.error.flatten(),
            'inuse_auto': [True for _ in lm.data.flatten()],
            'inuse_manual': [np.nan for _ in lm.data.flatten()],
            'time': lm.time.flatten(),
            'gate_id': np.concatenate([np.arange(-1, n_gates-1) for i in site_id]),
            'system_id': [0 for _ in lm.data.flatten()],
            'date':     np.concatenate([np.ones(n_gates, dtype=int)*x for x in lm.date]),
            'latitude': np.concatenate([np.ones( n_gates, dtype=float)*x for x in lm.location[:, 1]]),
            'longitude':np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 0]]),
            'elevation':np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 2]]),
            'daytime':  np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.daytime]),
        }

        n_sites,n_gates = hm.data.shape
        n_gates += 1

        hm.data = np.pad(hm.data, ((1,0), (1,0)), mode='constant', constant_values=np.nan)
        hm.time = np.pad(hm.time, ((1,0), (1,0)), mode='constant', constant_values=np.nan)
        hm.error = np.pad(hm.error, ((1,0), (1,0)), mode='constant', constant_values=np.nan)

        hm.date = np.pad(hm.date, (1,0), mode='constant', constant_values=np.nan)
        hm.location = np.pad(hm.location, ((1,0), (0,0)), mode='constant', constant_values=np.nan)

        hm.daytime = np.pad(hm.daytime, (1,0), mode='constant', constant_values=np.nan)

        data_avg['site_id']      = np.append(data_avg['site_id'], np.concatenate([np.ones(n_gates, dtype=int)*i for i in site_id]))
        data_avg['dbdt']         = np.append(data_avg['dbdt'], hm.data.flatten())
        data_avg['error']        = np.append(data_avg['error'], hm.error.flatten())
        data_avg['inuse_auto']   = np.append(data_avg['inuse_auto'], np.array([True for _ in hm.data.flatten()]))
        data_avg['inuse_manual'] = np.append(data_avg['inuse_manual'], np.array([np.nan for _ in hm.data.flatten()]))
        data_avg['time']         = np.append(data_avg['time'],      hm.time.flatten())
        data_avg['gate_id']      = np.append(data_avg['gate_id'],   np.concatenate([np.arange(-1, n_gates-1) for i in range(-1, n_sites)]))
        data_avg['system_id']    = np.append(data_avg['system_id'], np.array([1 for _ in hm.data.flatten()]))
        data_avg['date']         = np.append(data_avg['date'],      np.concatenate([np.ones(n_gates, dtype=int)*x for x in lm.date]))
        data_avg['latitude']     = np.append(data_avg['latitude'],  np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 1]]))
        data_avg['longitude']    = np.append(data_avg['longitude'], np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 0]]))
        data_avg['elevation']    = np.append(data_avg['elevation'], np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.location[:, 2]]))
        data_avg['daytime']      = np.append(data_avg['daytime'],   np.concatenate([np.ones(n_gates, dtype=float)*x for x in lm.daytime]))

        forward_operators = usf.sweep2fwr(sweeps)

        history = [f'place_holder = TEMframe.from_usf_folder(\"{folder_path}\")']

        df_data = cls(data_avg, forward_operators=forward_operators, history=history, track_history=track_history)
        # with df_data._skip_tracking():
        df_data.sort_values(by=['site_id','system_id', 'gate_id'], inplace=True)
        df_data.reset_index(drop=True, inplace=True)
        
        df_data['error_lb'] = df_data['dbdt']-df_data['dbdt']/(1. + df_data['error']/100.)
        df_data['error_ub'] = df_data['dbdt']*(1. + df_data['error']/100.)-df_data['dbdt']

        df_data['log10_dbdt'] = np.log10(np.abs(df_data['dbdt']))

        df_data['sys_gate'] = df_data['system_id'] + df_data['gate_id']/1e6
        df_data['data_id'] = np.arange(len(df_data))
        import utm
        ok = ~np.isnan(df_data['latitude']) & ~np.isnan(df_data['longitude'])
        utmx,utmy,zone_number,zone_letter = utm.from_latlon(df_data['latitude'].values[ok], df_data['longitude'].values[ok])
        df_data['utm_x'] = np.nan
        df_data['utm_y'] = np.nan
        df_data['zone_number'] = np.nan
        # df_data['zone_letter'] = np.nan
        df_data.loc[ok, 'utm_x'] = np.round(utmx, 1)
        df_data.loc[ok, 'utm_y'] = np.round(utmy, 1)
        df_data.loc[ok, 'zone_number'] = zone_number
        df_data.loc[ok, 'zone_letter'] = zone_letter
        ds = np.cumsum(np.sqrt(np.diff(utmx, prepend=utmx[0])**2 + np.diff(utmy, prepend=utmy[0])**2))
        df_data['distance'] = np.nan
        df_data.loc[ok, 'distance'] = np.round(ds, 1)

        # source_line = df_data._record_op()
        # output_name = source_line.split('=')[0].strip()
        # df_data.history[0] = df_data.history[0].replace('place_holder', output_name)
        # df_data.history.pop()  # remove the initial placeholder history entry
        df_data.track_history = track_history
        
        df_data.forward_operators[0].source     = df_data.forward_operators[1].source
        df_data.forward_operators[0].receiver   = df_data.forward_operators[1].receiver
        df_data.forward_operators[0].filterfunc = df_data.forward_operators[1].filterfunc        
        df_data.dmfwr = df_data.forward_operators[0]+df_data.forward_operators[1]

        return df_data
    
    def disable(self, data_ids):
        # self._record_op()
        # with self._skip_tracking():
        self['inuse_manual'] = self['inuse_manual'].mask(self['data_id'].isin(data_ids), False)

        return self
    
    def enable(self, data_ids):
        self['inuse_manual'] = self['inuse_manual'].mask(self['data_id'].isin(data_ids), True)
        return self

    @classmethod
    def from_pandas(cls, dataframe, **kwargs):
        return cls(dataframe, **kwargs)

    @classmethod
    def load(cls, file_path):
        df = pd.read_csv(file_path)
        return cls.from_pandas(df)

    # def __setitem__(self, key, value):
    #     self._record_op()
    #     return super().__setitem__(key, value)
    
    # def __getitem__(self, key):
    #     self._record_op()
    #     return super().__getitem__(key)
    
    def _record_op(self):
        source_line=None
        if self.track_history:
            stack = inspect.stack()
            if stack[2].code_context is not None:
                source_line = stack[2].code_context[0].strip()
                if source_line != self.history[-1]:
                    self.history.append(source_line)
        return source_line
    
    # @contextmanager
    # def _skip_tracking(self):
    #     original = self.track_history
    #     self.track_history = False
    #     try:
    #         yield
    #     finally:
    #         self.track_history = original

    def invert_individually(self, res_start, vc=0.4, hc=0.4, max_iterations=50):
#        res_start = LogResistivity.smooth(torch.ones(31)*40., torch.logspace(0, 2.1, 30))
        self._record_op()
        current_history = self.history.copy()
        dmfwr = self.dmfwr

        # with self._skip_tracking():
        df_data = self.copy()
        df_overview = df_data.overview()


        # this gives a warning and may need to updated if pandas is updated to pandas 3.0
        df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'])

        df_data['dbdt_syn'] = df_data['dbdt']*np.nan
        pivot_multi = df_data[(df_data['site_id']>-1)*(df_data['gate_id']>-1)].pivot_table(
            index=['site_id'],
            columns=['sys_gate'],
            values=['dbdt', 'error', 'include', 'data_id'],
        )
        pivot_multi['site_id'] = pivot_multi.index

        pivot_multi.columns = [f'{val}_{col}' for val, col in pivot_multi.columns]

        assert len(pivot_multi) == len(df_overview), "Expected 4 columns in pivot_multi"

        pivot_multi.sort_values(by='site_id', inplace=True)
        df_overview.sort_values(by='site_id', inplace=True)        
        results = []
        for i,((id_row, row), (id_meta, row_meta)) in enumerate(zip(pivot_multi.iterrows(), df_overview.iterrows())):
            assert id_meta == id_row, "Site ID mismatch between row and metadata"

            dbdt_values  = row.filter(like='dbdt_').values
            error_values = row.filter(like='error_').values
            include_values = row.filter(like='include_').values
            data_id = row.filter(like='data_id_').values

            d_obs = torch.from_numpy(dbdt_values).abs().log()
            d_err = torch.from_numpy(np.log1p(error_values/100.))
            include_mask = include_values.astype(bool)
            d_err[~include_mask] = torch.inf  # Set error to zero for included measurements

            inv = fastJac(d_obs, d_err, res_start, self.dmfwr)
            inv.data_misfit_acceptance_threshold = 0.95
            res_mod = inv.invert(iter_cap=10)



            d_syn = inv.forward(*res_mod.mod).exp()
            df_data.loc[data_id, 'dbdt_syn'] = d_syn.numpy()

            rho,thick = res_mod.mod
            row_meta['site_id'] = id_meta
            row_meta['resistivity'] = rho.detach().cpu().numpy().tolist()
            row_meta['thickness'] = thick.detach().cpu().numpy().tolist()
            results.append(row_meta.to_dict())
            print(f'{i+1:02d} of {len(pivot_multi):02d}', flush=True, end='\r')

        df_resmod = pd.DataFrame(results)

        rows = []
        for _, row in df_resmod.iterrows():
            site_id = row['site_id']
            resistivities = row['resistivity']
            thicknesses = row['thickness']
            tops = np.concatenate([[0], np.cumsum(thicknesses)[:-1]])
            bottoms = np.cumsum(thicknesses)
            bottoms[-1] = bottoms[-1]*1.1
            for i, (rho, top, bottom) in enumerate(zip(resistivities, tops, bottoms)):
                rows.append({
                    'site_id': site_id,
                    'daytime': row['daytime'],
                    'date': row['date'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'elevation': row['elevation'],
                    'layer': i,
                    'resistivity': rho,
                    'top_depth': top,
                    'bottom_depth': bottom,
                    'center_depth': (top + bottom) / 2
                })

            df_layers = TEMframe(rows, history=current_history.copy())
        self.history = current_history[:-1]
        return df_layers, df_data
    

    def get_site_data(self, site_id):
        df_data     = self[self['site_id']==site_id].copy()
        df_data     = df_data[df_data['gate_id']>-1]
        df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'].astype(bool))
        
        df_data.sort_values('data_id', inplace=True)
        dbdt=df_data['dbdt'].values
        d_obs = torch.from_numpy(np.abs(dbdt)).log()
        d_err = torch.from_numpy(np.log1p(df_data['error'].values/100))
        include_values = torch.from_numpy(df_data['include'].values.astype(bool))
        
        d_err[include_values==0] = torch.inf
        d_err[dbdt<0] = torch.inf
        return d_obs, d_err, self.__class__.from_pandas(df_data, history=self.history.copy(), forward_operators=self.forward_operators)
    

    def invert(self, res_start, vc=0.4, hc=0.4, max_iterations=20):
#        res_start = LogResistivity.smooth(torch.ones(31)*40., torch.logspace(0, 2.1, 30))
        # self._record_op()
        make_log()
        current_history = self.history.copy()
        dmfwr = self.dmfwr

        df_data = self.copy()
        df_overview = df_data.overview()


        # this gives a warning and may need to updated if pandas is updated to pandas 3.0
        df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'])

        df_data['dbdt_syn'] = df_data['dbdt']*np.nan
        pivot_multi = df_data[(df_data['site_id']>-1)*(df_data['gate_id']>-1)].pivot_table(
            index=['site_id'],
            columns=['sys_gate'],
            values=['dbdt', 'error', 'include', 'data_id'],
        )
        pivot_multi['site_id'] = pivot_multi.index
        
        pivot_multi.columns = [f'{val}_{col}' for val, col in pivot_multi.columns]

        assert len(pivot_multi) == len(df_overview), "Expected 4 columns in pivot_multi"

        pivot_multi.sort_values(by='site_id', inplace=True)
        df_overview.sort_values(by='site_id', inplace=True)        

        results  = []
        inv_list = []
        x_list,y_list = [],[]

        for i,((id_row, row), (id_meta, row_meta)) in enumerate(zip(pivot_multi.iterrows(), df_overview.iterrows())):
            assert id_meta == id_row, "Site ID mismatch between row and metadata"

            dbdt_values  = row.filter(like='dbdt_').values
            error_values = row.filter(like='error_').values
            include_values = row.filter(like='include_').values
            data_id = row.filter(like='data_id_').values

            d_obs = torch.from_numpy(dbdt_values).abs().log()
            d_err = torch.from_numpy(np.log1p(error_values/100.))
            include_mask = include_values.astype(bool)
            d_err[~include_mask] = torch.inf  # Set error to zero for included measurements

            inv = fastJac(d_obs, d_err, res_start.copy(), dmfwr.copy())
            inv.setup_matrices()
            inv_list.append(inv)
            x_list.append(row_meta['utm_x'])
            y_list.append(row_meta['utm_y'])
        
        inv = SCI(inv_list, x=np.array(x_list), y=np.array(y_list), log=write_log)
        inv.data_misfit_acceptance_threshold = 0.95
        res_mods = inv.invert(iter_cap=max_iterations)
        doi = inv.doi
        for i,((id_row, row), (id_meta, row_meta)) in enumerate(zip(pivot_multi.iterrows(), df_overview.iterrows())):
            assert id_meta == id_row, "Site ID mismatch between row and metadata"

            data_id = row.filter(like='data_id_').values    
            res_mod = res_mods[i].copy()

            d_syn = inv._dpredgrid[i].exp()
            df_data.loc[data_id, 'dbdt_syn'] = d_syn.numpy()
            
            
            rho,thick = res_mod.mod
            row_meta['site_id'] = id_meta
            row_meta['resistivity'] = rho.detach().cpu().numpy().tolist()
            row_meta['thickness'] = thick.detach().cpu().numpy().tolist()
            # row_meta['misfit'] = df_data.loc[data_id, 'misfit'].mean()
            
            results.append(row_meta.to_dict())
            print(f'Inversion for data_id {i:02d} completed.')
        df_data['misfit'] = (((df_data['dbdt'] - df_data['dbdt_syn'])**2/(np.log1p(df_data['dbdt'].values*df_data['error'].values/100.)**2))**0.5)
        df_data.dmfwr = self.dmfwr

        print(np.log1p(df_data['error'].values/100.), flush=True)
        df_overview = df_data.overview()
        df_resmod = pd.DataFrame(results)

        rows = []
        for _, row in df_resmod.iterrows():
            site_id = row['site_id']
            resistivities = row['resistivity']
            thicknesses = row['thickness']
            tops = np.concatenate([[0], np.cumsum(thicknesses)[:-1]])
            bottoms = np.cumsum(thicknesses)
            for i, (rho, top, bottom) in enumerate(zip(resistivities, tops, bottoms)):
                rows.append({
                    'site_id': site_id,
                    'daytime': row['daytime'],
                    'date': row['date'],
                    'latitude': row['latitude'],
                    'longitude': row['longitude'],
                    'elevation': row['elevation'],
                    'doi': doi[_], 
                    'layer': i,
                    'resistivity': rho,
                    'misfit': df_overview[df_overview.index==site_id]['misfit'].values[0],
                    'top_depth': top,
                    'bottom_depth': bottom,
                    'center_depth': (top + bottom) / 2
                })

        df_layers = TEMframe(rows, history=current_history.copy())
        # self.history = current_history[:-1]
        return df_layers, df_data


    def invert_site(self, site_id, vc=0.4, res_start=100., max_iterations=20):
        t_max = max([fwr.times.max().item() for fwr in self.forward_operators])
        d_max = (t_max*4e6)**0.5
        n_layers = 30

        if res_start is None:
            thk = 1.+torch.logspace(-0.5, np.log10(d_max-n_layers+1), n_layers).diff()
            z = thk.cumsum()
            res_start=LogResistivity.smooth(torch.ones(n_layers)*40., z)

        elif isinstance(res_start, float):
            thk = 1.+torch.logspace(-0.5, np.log10(d_max-n_layers+1), n_layers).diff()
            z = thk.cumsum(0)
            res_start=LogResistivity.smooth(torch.ones(n_layers)*res_start, z)
        d_obs, d_err, df_site = self.get_site_data(site_id)

        inv1 = fastJac(d_obs, d_err, res_start, self.dmfwr)
        inv1.vertical_smoothness=vc
        res_mod=inv1.invert(iter_cap=max_iterations)
        i,row = df_site.overview().iterrows().__next__()
        d_syn = inv1.data_predicted.exp()
        df_site.loc[:, 'dbdt_syn'] = d_syn.numpy()

        rho,thick = res_mod.mod
        rows = []
        tops = np.concatenate([[0], np.cumsum(thick)[:-1]])
        bottoms = np.cumsum(thick)

        for i, (rho, top, bottom) in enumerate(zip(rho, tops, bottoms)):
            rows.append({
                'site_id': df_site['site_id'].values[0],
                'daytime': row['daytime'],
                'date': row['date'],
                'latitude': row['latitude'],
                'longitude': row['longitude'],
                'elevation': row['elevation'],
                'layer': i,
                'resistivity': rho,
                'top_depth': top,
                'bottom_depth': bottom,
                'center_depth': (top + bottom) / 2
            })
        df_layers = self.__class__(rows, history=self.history, forward_operators=self.forward_operators)
        return df_layers, df_site, inv1

    def save(self, save_folder):
        tem_data = os.path.join(save_folder, 'tem_data.csv')
        self.to_csv(tem_data, index=False)
        with open(os.path.join(save_folder, 'history.py'), 'w') as f:
            for line in self.history:
                f.write(f'{line}\n')
        for i,fwr in enumerate(self.forward_operators):
            save_folder_fwr = os.path.join(save_folder, f'fwr{i}')
            fwr.save(save_folder_fwr)
    
    @classmethod
    def load(cls, load_folder):
        tem_data = os.path.join(load_folder, 'tem_data.csv')
        df = pd.read_csv(tem_data)
        history = []
        history_file = os.path.join(load_folder, 'history.py')
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = f.readlines()
            history = [line.strip() for line in history]
        forward_operators = []
        i = 0
        from anemone.forwards import Forward, logify_forward
        lg_FWR = logify_forward(Forward)

        while True:
            save_folder_fwr = os.path.join(load_folder, f'fwr{i}')
            if os.path.exists(save_folder_fwr):
                fwr = lg_FWR.load(save_folder_fwr)
                forward_operators.append(fwr)
                i += 1
            else:
                break
        return cls.from_pandas(df, history=history, forward_operators=forward_operators)
    
    def copy(self, *args, **kwargs):
        return TEMframe(super().copy(*args, **kwargs), history=self.history, forward_operators=self.forward_operators)
