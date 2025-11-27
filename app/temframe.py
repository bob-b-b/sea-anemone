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
        self.__post_init__()

    def overview(self):
        current_history = self.history.copy()
        tmp_df = self.copy()
        with tmp_df._skip_tracking():
            df = self.pivot_table(
                index=['site_id'],
                values=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'],
                aggfunc='first'
            )

        with self._skip_tracking():
            res = TEMframe(df, history=current_history.copy())
        res.track_history = self.track_history
        res._record_op()
        self.history = current_history
        return res

    @classmethod
    def from_zip(cls, zip_content, track_history=True):
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
            for fname in usf_files:
                with z.open(fname, 'r') as f:
                    sweeps += usf.Sweep.from_buffer(f, combine=False)
            return cls.from_sweeps(sweeps, track_history=track_history, folder_path=z.namelist()[0]+'.zip')

    @classmethod
    def from_session(cls, session_zip):
        import zipfile
        import io
        import base64

        df_data = None
        df_overview = None
        df_models = None

        if isinstance(session_zip, str) and session_zip.endswith('.zip'):
            with open(session_zip, 'rb') as f:
                zip_bytes = f.read()
        elif isinstance(session_zip, str):
            zip_bytes = base64.b64decode(session_zip)
        else:
            zip_bytes = session_zip

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            
            with z.open('tem_data.csv', 'r') as f:
                df = pd.read_csv(f)
            with z.open('history.py', 'r') as f:
                history = f.readlines()
            history = [line.strip().decode('utf-8') for line in history]
            
            saved_forwards = [x for x in z.namelist() if x.endswith('.em1')]
            forward_operators = None
            if len(saved_forwards) > 0:
                from anemone.forwards import Forward, logify_forward
                lg_FWR = logify_forward(Forward)
                forward_operators = []
                for i in range(len(saved_forwards)):
                    with z.open(saved_forwards[i], 'r') as f:
                        fwr = lg_FWR.load(f)
                        fwr.tolerance=1e-6
                        forward_operators.append(fwr)
            df_data = cls.from_pandas(df, history=history, forward_operators=forward_operators)
            df_overview = df_data.overview()
            if 'models.csv' in z.namelist():
                with z.open('models.csv', 'r') as f:
                    df_models = pd.read_csv(f)
                    df_models = cls.from_pandas(df_models, history=history, forward_operators=forward_operators)
        return {'data': df_data, 'models': df_models, 'overview':df_overview}

    @classmethod
    def from_usf_folder(cls, folder_path, track_history=True):
        sweeps = []
        usf_files = [folder_path+f for f in os.listdir(folder_path) if f.endswith('.usf')]
        for usf_file in usf_files:        
            with open(usf_file, 'rb') as f:
                sweeps += usf.Sweep.from_buffer(f, combine=False)
        return cls.from_sweeps(sweeps, track_history=track_history, folder_path=folder_path)

    @classmethod
    def from_sweeps(cls, sweeps, track_history=True, folder_path=None):
        points = set([x.points for x in sweeps])
        mega_sweeps = []
        for pnts in points:
            mega_sweeps.append(usf.Sweep.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
        lm,hm = mega_sweeps

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
        with df_data._skip_tracking():
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
            df_data['zone_letter'] = np.nan
            df_data.loc[ok, 'utm_x'] = utmx
            df_data.loc[ok, 'utm_y'] = utmy
            df_data.loc[ok, 'zone_number'] = zone_number
            df_data.loc[ok, 'zone_letter'] = zone_letter
            ds = np.cumsum(np.sqrt(np.diff(utmx, prepend=utmx[0])**2 + np.diff(utmy, prepend=utmy[0])**2))
            df_data['distance'] = np.nan
            df_data.loc[ok, 'distance'] = ds

        source_line = df_data._record_op()
        output_name = source_line.split('=')[0].strip()
        df_data.history[0] = df_data.history[0].replace('place_holder', output_name)
        df_data.history.pop()  # remove the initial placeholder history entry
        df_data.track_history = track_history

        return df_data
    
    def disable(self, data_ids):
        self._record_op()
        with self._skip_tracking():
            self['inuse_manual'] = self['inuse_manual'].mask(self['data_id'].isin(data_ids), False)

        return self
    
    def enable(self, data_ids):
        self._record_op()
        with self._skip_tracking():
            self['inuse_manual'] = self['inuse_manual'].mask(self['data_id'].isin(data_ids), True)
        return self

    @classmethod
    def from_pandas(cls, dataframe, **kwargs):
        return cls(dataframe, **kwargs)

    @classmethod
    def load(cls, file_path):
        df = pd.read_csv(file_path)
        return cls.from_pandas(df)

    def __setitem__(self, key, value):
        self._record_op()
        return super().__setitem__(key, value)
    
    def __getitem__(self, key):
        self._record_op()
        return super().__getitem__(key)
    
    def _record_op(self):
        source_line=None
        if self.track_history:
            stack = inspect.stack()
            if stack[2].code_context is not None:
                source_line = stack[2].code_context[0].strip()
                if source_line != self.history[-1]:
                    self.history.append(source_line)
        return source_line
    
    @contextmanager
    def _skip_tracking(self):
        original = self.track_history
        self.track_history = False
        try:
            yield
        finally:
            self.track_history = original

    def invert_individually(self, res_start, vc=0.4, hc=0.4, max_iterations=50):
#        res_start = LogResistivity.smooth(torch.ones(31)*40., torch.logspace(0, 2.1, 30))
        self._record_op()
        current_history = self.history.copy()

        self.forward_operators[0].source     = self.forward_operators[1].source
        self.forward_operators[0].receiver   = self.forward_operators[1].receiver
        self.forward_operators[0].filterfunc = self.forward_operators[1].filterfunc

        dmfwr = self.forward_operators[0]+self.forward_operators[1]

        with self._skip_tracking():
            df_data = self.copy()
            df_overview = df_data.overview()


            # this gives a warning and may need to updated if pandas is updated to pandas 3.0
            df_data['include'] = df_data['inuse_manual'].fillna(df_data['inuse_auto'])

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

                inv = fastJac(d_obs, d_err, res_start, dmfwr, logger=print)
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
    
    def invert(self, res_start, vc=0.4, hc=0.4, max_iterations=50):
#        res_start = LogResistivity.smooth(torch.ones(31)*40., torch.logspace(0, 2.1, 30))
        self._record_op()
        current_history = self.history.copy()

        self.forward_operators[0].source     = self.forward_operators[1].source
        self.forward_operators[0].receiver   = self.forward_operators[1].receiver
        self.forward_operators[0].filterfunc = self.forward_operators[1].filterfunc

        dmfwr = self.forward_operators[0]+self.forward_operators[1]

        with self._skip_tracking():
            df_data = self.copy()
            df_overview = df_data.overview()


            # this gives a warning and may need to updated if pandas is updated to pandas 3.0
            df_data['include'] = df_data['inuse_manual'].fillna(df_data['inuse_auto'])

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

                inv = fastJac(d_obs, d_err, res_start.copy(), dmfwr.copy(), logger=silence)
                inv.setup_matrices()
                inv_list.append(inv)
                x_list.append(row_meta['utm_x'])
                y_list.append(row_meta['utm_y'])

            inv = SCI(inv_list, x=np.array(x_list), y=np.array(y_list))
            inv.data_misfit_acceptance_threshold = 0.95
            res_mods = inv.invert(iter_cap=max_iterations)

            for i,((id_row, row), (id_meta, row_meta)) in enumerate(zip(pivot_multi.iterrows(), df_overview.iterrows())):
                assert id_meta == id_row, "Site ID mismatch between row and metadata"

                data_id = row.filter(like='data_id_').values    
                res_mod = res_mods[i].copy()

                d_syn = inv_list[i].forward(*res_mod.mod).exp()
                df_data.loc[data_id, 'dbdt_syn'] = d_syn.numpy()

                rho,thick = res_mod.mod
                row_meta['site_id'] = id_meta
                row_meta['resistivity'] = rho.detach().cpu().numpy().tolist()
                row_meta['thickness'] = thick.detach().cpu().numpy().tolist()
                results.append(row_meta.to_dict())
                print(f'Inversion for data_id {i:02d} completed.')

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
                        'layer': i,
                        'resistivity': rho,
                        'top_depth': top,
                        'bottom_depth': bottom,
                        'center_depth': (top + bottom) / 2
                    })

            df_layers = TEMframe(rows, history=current_history.copy())
        self.history = current_history[:-1]
        return df_layers, df_data
    
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
                fwr.tolerance=1e-6
                forward_operators.append(fwr)
                i += 1
            else:
                break
        return cls.from_pandas(df, history=history, forward_operators=forward_operators)




    def __post_init__(self):
        def wrapped_method(func):
            def wrapped(*args, **kwargs):
                result = func(*args, **kwargs)
                return TEMframe.from_pandas(result, history=self.history.copy(), forward_operators=self.forward_operators.copy())
            return wrapped
        # This is the code to figure out what to wrap. leaving these loops takes considerably longer to run.
        
        # all_vars = dir(DataFrame)
        # all_vars.remove('_data')
        # for var in all_vars:
        #     try:
        #         method = getattr(self, var, None)
        #         if callable(method):
        #                 sig = inspect.signature(method)
        #                 return_annotation = getattr(sig, 'return_annotation', None)
        #                 if return_annotation == 'DataFrame':
        #                     wrapped_method = wrap_output(method)
        #                     setattr(self, var, wrapped_method)
        #                     print('\t\tsetattr(self, \'{}\', wrapped_method(self.{}))'.format(var, var))
        #     except:
        #         pass
        setattr(self, '__rmatmul__', wrapped_method(self.__rmatmul__))
        setattr(self, '_append', wrapped_method(self._append))
        setattr(self, '_arith_method_with_reindex', wrapped_method(self._arith_method_with_reindex))
        setattr(self, '_construct_result', wrapped_method(self._construct_result))
        setattr(self, '_constructor_from_mgr', wrapped_method(self._constructor_from_mgr))
        setattr(self, '_dispatch_frame_op', wrapped_method(self._dispatch_frame_op))
        setattr(self, '_reindex_multi', wrapped_method(self._reindex_multi))
        setattr(self, 'add', wrapped_method(self.add))
        setattr(self, 'applymap', wrapped_method(self.applymap))
        setattr(self, 'assign', wrapped_method(self.assign))
        setattr(self, 'combine', wrapped_method(self.combine))
        setattr(self, 'combine_first', wrapped_method(self.combine_first))
        setattr(self, 'compare', wrapped_method(self.compare))
        setattr(self, 'corr', wrapped_method(self.corr))
        setattr(self, 'cov', wrapped_method(self.cov))
        setattr(self, 'diff', wrapped_method(self.diff))
        setattr(self, 'div', wrapped_method(self.div))
        setattr(self, 'divide', wrapped_method(self.divide))
        setattr(self, 'eq', wrapped_method(self.eq))
        setattr(self, 'explode', wrapped_method(self.explode))
        setattr(self, 'floordiv', wrapped_method(self.floordiv))
        setattr(self, 'from_dict', wrapped_method(self.from_dict))
        setattr(self, 'from_records', wrapped_method(self.from_records))
        setattr(self, 'ge', wrapped_method(self.ge))
        setattr(self, 'gt', wrapped_method(self.gt))
        setattr(self, 'isin', wrapped_method(self.isin))
        setattr(self, 'isna', wrapped_method(self.isna))
        setattr(self, 'isnull', wrapped_method(self.isnull))
        setattr(self, 'join', wrapped_method(self.join))
        setattr(self, 'le', wrapped_method(self.le))
        setattr(self, 'lt', wrapped_method(self.lt))
        setattr(self, 'map', wrapped_method(self.map))
        setattr(self, 'melt', wrapped_method(self.melt))
        setattr(self, 'merge', wrapped_method(self.merge))
        setattr(self, 'mod', wrapped_method(self.mod))
        setattr(self, 'mode', wrapped_method(self.mode))
        setattr(self, 'mul', wrapped_method(self.mul))
        setattr(self, 'multiply', wrapped_method(self.multiply))
        setattr(self, 'ne', wrapped_method(self.ne))
        setattr(self, 'nlargest', wrapped_method(self.nlargest))
        setattr(self, 'notna', wrapped_method(self.notna))
        setattr(self, 'notnull', wrapped_method(self.notnull))
        setattr(self, 'nsmallest', wrapped_method(self.nsmallest))
        setattr(self, 'pivot', wrapped_method(self.pivot))
        setattr(self, 'pivot_table', wrapped_method(self.pivot_table))
        setattr(self, 'pow', wrapped_method(self.pow))
        setattr(self, 'radd', wrapped_method(self.radd))
        setattr(self, 'rdiv', wrapped_method(self.rdiv))
        setattr(self, 'reindex', wrapped_method(self.reindex))
        setattr(self, 'reorder_levels', wrapped_method(self.reorder_levels))
        setattr(self, 'rfloordiv', wrapped_method(self.rfloordiv))
        setattr(self, 'rmod', wrapped_method(self.rmod))
        setattr(self, 'rmul', wrapped_method(self.rmul))
        setattr(self, 'round', wrapped_method(self.round))
        setattr(self, 'rpow', wrapped_method(self.rpow))
        setattr(self, 'rsub', wrapped_method(self.rsub))
        setattr(self, 'rtruediv', wrapped_method(self.rtruediv))
        setattr(self, 'set_axis', wrapped_method(self.set_axis))
        setattr(self, 'shift', wrapped_method(self.shift))
        setattr(self, 'sub', wrapped_method(self.sub))
        setattr(self, 'subtract', wrapped_method(self.subtract))
        setattr(self, 'swaplevel', wrapped_method(self.swaplevel))
        setattr(self, 'to_period', wrapped_method(self.to_period))
        setattr(self, 'to_timestamp', wrapped_method(self.to_timestamp))
        setattr(self, 'transform', wrapped_method(self.transform))
        setattr(self, 'transpose', wrapped_method(self.transpose))
        setattr(self, 'truediv', wrapped_method(self.truediv))
        setattr(self, '__rmatmul__', wrapped_method(self.__rmatmul__))
        setattr(self, '_append', wrapped_method(self._append))
        setattr(self, '_arith_method_with_reindex', wrapped_method(self._arith_method_with_reindex))
        setattr(self, '_construct_result', wrapped_method(self._construct_result))
        setattr(self, '_constructor_from_mgr', wrapped_method(self._constructor_from_mgr))
        setattr(self, '_dispatch_frame_op', wrapped_method(self._dispatch_frame_op))
        setattr(self, '_reindex_multi', wrapped_method(self._reindex_multi))
        setattr(self, 'add', wrapped_method(self.add))
        setattr(self, 'applymap', wrapped_method(self.applymap))
        setattr(self, 'assign', wrapped_method(self.assign))
        setattr(self, 'combine', wrapped_method(self.combine))
        setattr(self, 'combine_first', wrapped_method(self.combine_first))
        setattr(self, 'compare', wrapped_method(self.compare))
        setattr(self, 'corr', wrapped_method(self.corr))
        setattr(self, 'cov', wrapped_method(self.cov))
        setattr(self, 'diff', wrapped_method(self.diff))
        setattr(self, 'div', wrapped_method(self.div))
        setattr(self, 'divide', wrapped_method(self.divide))
        setattr(self, 'eq', wrapped_method(self.eq))
        setattr(self, 'explode', wrapped_method(self.explode))
        setattr(self, 'floordiv', wrapped_method(self.floordiv))
        setattr(self, 'from_dict', wrapped_method(self.from_dict))
        setattr(self, 'from_records', wrapped_method(self.from_records))
        setattr(self, 'ge', wrapped_method(self.ge))
        setattr(self, 'gt', wrapped_method(self.gt))
        setattr(self, 'isin', wrapped_method(self.isin))
        setattr(self, 'isna', wrapped_method(self.isna))
        setattr(self, 'isnull', wrapped_method(self.isnull))
        setattr(self, 'join', wrapped_method(self.join))
        setattr(self, 'le', wrapped_method(self.le))
        setattr(self, 'lt', wrapped_method(self.lt))
        setattr(self, 'map', wrapped_method(self.map))
        setattr(self, 'melt', wrapped_method(self.melt))
        setattr(self, 'merge', wrapped_method(self.merge))
        setattr(self, 'mod', wrapped_method(self.mod))
        setattr(self, 'mode', wrapped_method(self.mode))
        setattr(self, 'mul', wrapped_method(self.mul))
        setattr(self, 'multiply', wrapped_method(self.multiply))
        setattr(self, 'ne', wrapped_method(self.ne))
        setattr(self, 'nlargest', wrapped_method(self.nlargest))
        setattr(self, 'notna', wrapped_method(self.notna))
        setattr(self, 'notnull', wrapped_method(self.notnull))
        setattr(self, 'nsmallest', wrapped_method(self.nsmallest))
        setattr(self, 'pivot', wrapped_method(self.pivot))
        setattr(self, 'pivot_table', wrapped_method(self.pivot_table))
        setattr(self, 'pow', wrapped_method(self.pow))
        setattr(self, 'radd', wrapped_method(self.radd))
        setattr(self, 'rdiv', wrapped_method(self.rdiv))
        setattr(self, 'reindex', wrapped_method(self.reindex))
        setattr(self, 'reorder_levels', wrapped_method(self.reorder_levels))
        setattr(self, 'rfloordiv', wrapped_method(self.rfloordiv))
        setattr(self, 'rmod', wrapped_method(self.rmod))
        setattr(self, 'rmul', wrapped_method(self.rmul))
        setattr(self, 'round', wrapped_method(self.round))
        setattr(self, 'rpow', wrapped_method(self.rpow))
        setattr(self, 'rsub', wrapped_method(self.rsub))
        setattr(self, 'rtruediv', wrapped_method(self.rtruediv))
        setattr(self, 'set_axis', wrapped_method(self.set_axis))
        setattr(self, 'shift', wrapped_method(self.shift))
        setattr(self, 'sub', wrapped_method(self.sub))
        setattr(self, 'subtract', wrapped_method(self.subtract))
        setattr(self, 'swaplevel', wrapped_method(self.swaplevel))
        setattr(self, 'to_period', wrapped_method(self.to_period))
        setattr(self, 'to_timestamp', wrapped_method(self.to_timestamp))
        setattr(self, 'transform', wrapped_method(self.transform))
        setattr(self, 'transpose', wrapped_method(self.transpose))
        setattr(self, 'truediv', wrapped_method(self.truediv))