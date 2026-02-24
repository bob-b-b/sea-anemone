import dash_bootstrap_components as dbc
from dash import  html, Output, Input, dcc, State,ALL, MATCH
from dash.exceptions import PreventUpdate

import dash_flexlayout as dfl

from dataclasses import dataclass
from dataclasses_jsonschema import JsonSchemaMixin
import tkinter as tk

import plotly.express as px




def gear_maker(id):
    gear = html.Div(
        html.Span(
            [html.Img(id=id+'_gear', src="./assets/settings.svg", style={'height': '0.5cm'})],
            style={'cursor': 'pointer', 'position': 'absolute', 'bottom': '0', 'right': '0'}
        ),
    )
    return gear

def find_tab_by_id(tabs, tab_id, path=None):
    if path is None: path = []

    if isinstance(tabs, dict):
        if 'id' in tabs and tabs['id'] == tab_id:
            return path
        for key, value in tabs.items():
            if isinstance(value, (dict, list)):
                new_path = find_tab_by_id(value, tab_id, path=path + [key])
                if new_path:  # If a valid path is found, return it
                    return new_path
    elif isinstance(tabs, list):
        for i, item in enumerate(tabs):
            new_path = find_tab_by_id(item, tab_id, path=path + [i])
            if new_path:  # If a valid path is found, return it
                return new_path
    return None

def update_tabset(json_data, target_tab_id, settings_tab_id, change_order=False):
    accessor_chain = find_tab_by_id(json_data, target_tab_id)
    accessor_string = ''
    for key in accessor_chain[:-1]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    tablist = eval('json_data' + accessor_string)
    tabset = [x['id'] for x in eval('json_data' + accessor_string)]
    idx = tabset.index(target_tab_id)
    if settings_tab_id not in tabset:
        tablist.insert(idx+1, {
            'type': 'tab',
            'id': settings_tab_id,
            'name': target_tab_id.replace('tab-', '')+' settings',
            'component': 'text',
        })
        tabset.insert(idx+1, settings_tab_id)
    elif change_order:
        ctab = tablist.pop(tabset.index(settings_tab_id))
        tablist.insert(idx+1, ctab)

    accessor_string = ''
    for key in accessor_chain[:-2]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    exec(f'json_data{accessor_string}[\'selected\'] = {tabset.index(settings_tab_id)}')
    return json_data

def close_settings(json_data, target_tab_id, settings_tab_id):
    accessor_chain = find_tab_by_id(json_data, settings_tab_id)
    accessor_string = ''
    for key in accessor_chain[:-1]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    tablist = eval('json_data' + accessor_string)
    tabset = [x['id'] for x in eval('json_data' + accessor_string)]
    idx = tabset.index(settings_tab_id)
    tablist.pop(idx)
    tabset.pop(idx)

    accessor_string = ''
    for key in accessor_chain[:-2]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    
    exec(f'json_data{accessor_string}[\'selected\'] = {tabset.index(target_tab_id)}')
    return json_data

def add_tabset(json_data, new_tab, target_tab_id, settings_tab_id, change_order=False):
    accessor_chain = find_tab_by_id(json_data, new_tab)
    accessor_string = ''
    for key in accessor_chain[:-1]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    tablist = eval('json_data' + accessor_string)
    tabset = [x['id'] for x in eval('json_data' + accessor_string)]
    idx = tabset.index(new_tab)
    if new_tab not in tabset:
        tablist.insert(idx+1, {
            'type': 'tab',
            'id': settings_tab_id,
            'name': target_tab_id.replace('tab-', '')+' settings',
            'component': 'text',
        })
        tabset.insert(idx+1, settings_tab_id)
    elif change_order:
        ctab = tablist.pop(tabset.index(settings_tab_id))
        tablist.insert(idx+1, ctab)

    accessor_string = ''
    for key in accessor_chain[:-2]:
        if isinstance(key, int):
            accessor_string += f'[{key}]'
        else:
            accessor_string += f'["{key}\"]'
    exec(f'json_data{accessor_string}[\'selected\'] = {tabset.index(settings_tab_id)}')
    return json_data




@dataclass
class PanelSettings:
    id: str
    _settings_schema: dict = None
    title: str = None
    def __init__(self, id):
        self.id = id

    def __post_init__(self):
        for key in self.schema.get('properties', {}).keys():
            try:
                if self.schema['properties'][key]['type'] == 'array':
                    if eval(f'self.{key}') is not None:
                        exec(f'self.{key}_len = len(self.{key})')
                    else:
                        exec(f'self.{key}_len = 0')
            except KeyError:
                pass

    def initialize(self):
        # Main panel content (to be overridden by subclasses)
        return html.Div([html.H3(f"Panel: {self.id}")])

    def special_renders(self):
        color_check = lambda key,prop: 'color' in key.lower()
        def color_render(key, prop):
            return dbc.Input(
                type='color',
                id={'type': f'settings-{self.id}', 'key': key},
                value=eval(f'self.{key}'),
                style={'width':'50px', 'height':'30px'}
            )
        enum_check = lambda key, prop: 'enum' in prop
        def enum_render(key, prop):
            return dbc.Select(
                options=[{"label": v, "value": v} for v in prop['enum']],
                id={'type': f'settings-{self.id}', 'key': key},
                value=eval(f'self.{key}'),
                style={'margin': '5px'}
            )
        return [
            (color_check, color_render),
            (enum_check,  enum_render)
        ]

    def render(self):
        # Render settings form based on JSON schema
        if self.schema is None:
            return html.Div("No settings available.")
        form_items = [dcc.Markdown(f'# {self.id} settings') if self.title is None else dcc.Markdown(f'# {self.title}')]

        special_renders = self.special_renders()
        n_special_renders = len(special_renders)

        for key, prop in self.schema.get('properties', {}).items():
            row_children = []
            row_children.append(dbc.Label(prop.get('title', key), style={'marginRight': '10px'}))

            n_render = 0
            for check, render in special_renders:
                if check(key, prop):
                    row_children.append(render(key, prop))
                    break
                else:
                    n_render += 1
            if n_render == n_special_renders:
                input_type = 'text'
                if prop.get('type') == 'number':
                    input_type = 'number'
                elif prop.get('type') == 'boolean':
                    input_type = 'checkbox'
                row_children.append(
                    dbc.Input(
                        type=input_type,
                        id={'type': f'settings-{self.id}', 'key': key},
                        value=eval(f'self.{key}'),
                        debounce=True,
                        style={'margin': '5px'}
                    )
                )
            form_items.append(dbc.Row(row_children, className='mb-2'))
        # Add a save button
        form_items.append(dbc.Button(
            "Save Settings",
            id=f'{self.id}_settings_save',
            n_clicks=0,
            style={'margin': '10px'}
        ))
        # Add a load button
        form_items.append(dbc.Button(
            "Load Settings",
            id=f'{self.id}_settings_load',
            n_clicks=0,
            style={'margin': '10px'}
        ))

        return html.Div([dbc.Form(form_items, style={'margin': '10px'}), 
                         gear_maker(self.id+'_settings')], style={'width':'95%'})

    def node(self):
        return dfl.Tab(id=f'tab-{self.id}_settings', children=[self.render()])
    
    def update_attributes(self, data_dict):
        for key, value in data_dict.items():
            if hasattr(self, key):
                # Convert numeric strings to floats if necessary
                if isinstance(value, str) and value.replace('.', '', 1).isdigit():
                    value = float(value)
                setattr(self, key, value)

    @classmethod
    def _create_schema(cls):
        class tmp(cls, JsonSchemaMixin):
            pass
        # return tmp.json_schema()
        schema = tmp.json_schema()
        
        # Target the property and force it to be an integer-based slider/input
        if 'properties' in schema and 'column_width' in schema['properties']:
            schema['properties']['column_width'].update({
                "type": "integer",    # Tell UI to treat this as a whole number
                "title": "Bar Width (1-9)",
                "minimum": 1,         # Start at 1 (becomes 0.1)
                "maximum": 9,         # End at 9 (becomes 0.9)
                "step": 1             # Increment by 1
            })
        return schema
    
    @property
    def schema(self):
        if self._settings_schema is None:
            tmp = self.__class__._create_schema()
            tmp['properties'].pop('_settings_schema')
            tmp['properties'].pop('id')
            tmp['properties'].pop('title')  # Remove title if it exists
            self._settings_schema = tmp
        return self._settings_schema
    
    @property
    def settings(self):
        return {k: getattr(self, k) for k in self.schema.get('properties', {}).keys() if hasattr(self, k)}
    
    @property
    def layout_dict(self):
        return {
            'type': 'tab',
            'id': f'tab-{self.id}_settings',
            'name': f'{self.id.lower()} settings',
        }
    
    def save_settings(self, fname):
        import json
        with open(fname, 'w') as f:
            json.dump(self.settings, f, indent=4)
    
    def load_settings(self, fname):
        import json
        with open(fname, 'r') as f:
            settings = json.load(f)
        for key, value in settings.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def add_callbacks(self, app):
        @app.callback(
            Output(f'{self.id}_settings_save', 'n_clicks'),
            [Input(f'{self.id}_settings_save', 'n_clicks')],
            prevent_initial_call=True
        )
        def save_settings(n_clicks):
            if n_clicks:
                root = tk.Tk()
                root.withdraw()  # Hide the root window
                root.attributes('-topmost', True)
                root.lift()
                root.focus_force()
                root.update()
                
                fname = filedialog.asksaveasfilename(
                    title="Save Settings",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    initialfile=f"{self.id}_settings.json",
                    parent=root
                )

                if fname:
                    self.save_settings(fname)
                root.destroy()
            return n_clicks
        
        @app.callback(
            Output(f'tab-{self.id}_settings', 'children'),
            [Input(f'{self.id}_settings_load', 'n_clicks')],
            prevent_initial_call=True
        )
        def load_settings(n_clicks):
            if n_clicks:
                root = tk.Tk()
                root.withdraw()
                root.attributes('-topmost', True)
                root.lift()
                root.focus_force()
                root.update()
                fname = filedialog.askopenfilename(
                    title="Load Settings",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    parent=root
                )
                if fname:
                    self.load_settings(fname)
                root.destroy()
            return self.render()
        
        @app.callback(
            Output('flex-layout', 'model', allow_duplicate=True),
            Input(f'{self.id}_gear', 'n_clicks'),
            State('flex-layout', 'model'),
            prevent_initial_call=True
        )
        def show_settings(n_clicks, model):
            if n_clicks:
                return update_tabset(model, f'tab-{self.id}', f'tab-{self.id}_settings', change_order=True)
            else:
                raise PreventUpdate        
        
        @app.callback(
            Output('flex-layout', 'model', allow_duplicate=True),
            Input(self.id+'_settings_gear', 'n_clicks'),
            State('flex-layout', 'model'),
            prevent_initial_call=True
        )
        def hide_settings(n_clicks, model):
            if n_clicks:
                return close_settings(model, f'tab-{self.id}', f'tab-{self.id}_settings')
            else:
                raise PreventUpdate
            

        @app.callback(
            Output('global-colorbar-store', 'data', allow_duplicate=True),
            Input({'type': f'settings-{self.id}', 'key': ALL}, 'value'),
            State({'type': f'settings-{self.id}', 'key': ALL}, 'id'),
            State('global-colorbar-store', 'data'),
            prevent_initial_call=True
        )
        def sync_to_global(values, ids, master_data):
            if master_data is None: master_data = {}
            
            # 1. Identify which attribute we are currently looking at (e.g., 'resistivity')
            # You might get this from a State('points-attr', 'value') 
            current_attr = 'resistivity' 
            
            if current_attr not in master_data:
                master_data[current_attr] = {}

            # 2. Map every UI change to the store
            for val, ident in zip(values, ids):
                key = ident['key']
                master_data[current_attr][key] = val
            
            # 3. Handle Special Logic (e.g., if colors change, update cmap)
            # This allows 'lm_color' or 'hm_color' to affect the visuals immediately
            return master_data
        
        import time
        
        @app.callback(
            # Output('force-refresh-store', 'data',allow_duplicate=True),
            Output(f"tab-{self.id}_settings", "data-status"), # Dummy output to trigger the callback
            Input({'type': f'settings-{self.id}', 'key': ALL}, 'value'),
            State({'type': f'settings-{self.id}', 'key': ALL}, 'id'),
            prevent_initial_call=True
        )

        def update_settings_realtime(values, ids):
            # 1. Update THIS object instance
            for val, identifier in zip(values, ids):
                key = identifier['key']
                
                # FIX: More robust numeric conversion
                if val is not None and str(val).replace('.', '', 1).isdigit():
                    # val = float(val)
                    try:
                        if float(val) == int(float(val)):
                            val = int(float(val))
                        else:
                            val = float(val)
                    except ValueError:
                        pass

                if hasattr(self, key):
                    setattr(self, key, val)

            print(f"Real-time update for {self.id}: vmin={self.vmin}, vmax={self.vmax}")
            return  "updated"

    @property
    def flat_keys(self):
        all_keys = list(self.schema.get('properties', {}).keys())
        key_elements = []
        for key in all_keys:
            if self.schema['properties'][key].get('type') == 'array':
                all_keys.remove(key)  # Remove list types from callbacks
                key_elements += [key+'-'+ str(i) for i in range(eval(f'self.{key}_len'))]
        all_keys = all_keys + key_elements
        return all_keys

@dataclass
class Panel:
    id: str
    settings: PanelSettings = None
    childname: str = 'figure'
    change_count: int = 0

    def add_callbacks(self, app):
        if self.settings is not None:
            self.settings.add_callbacks(app)

            if not self.settings.flat_keys:
                        return

            # # def update_render(*args):
            # def update_render(global_data, current_attr, *args):
            #     # 1. Update local settings from Global Store before rendering
            #     if global_data and current_attr in global_data:
            #         config = global_data[current_attr]
            #         # Assuming your settings object has these attributes
            #         if hasattr(self.settings, 'vmin'): self.settings.vmin = config['vmin']
            #         if hasattr(self.settings, 'vmax'): self.settings.vmax = config['vmax']
            #         if hasattr(self.settings, 'log'): self.settings.log = config['log']


            #     for key, arg in zip(self.settings.flat_keys, args):
            #         if isinstance(arg, dict) and 'hex' in arg:
            #             arg = arg['hex']
                    
            #         if hasattr(self.settings, key):
            #             # print("KEY HERE", key)
            #             # print('type',self.settings.schema['properties'][key].get('type') )
            #             if self.settings.schema['properties'][key].get('type')=='integer':
            #                 arg = int(arg)
            #             elif self.settings.schema['properties'][key].get('type')=='number':
            #                 arg = float(arg)
            #             elif self.settings.schema['properties'][key].get('type')=='boolean':
            #                 arg = (arg=='true' or arg is True)
            #             setattr(self.settings, key, arg)
            #         elif '-' in key:
            #             basekey,index = key.split('-')
            #             if hasattr(self.settings, basekey):
            #                 arg = (arg=='true' or arg is True)
            #                 exec(f'self.settings.{basekey}[{index}] = arg')
            #     return self.render()        
            
            # update_render = app.callback(Output(self.id, self.childname),#, allow_duplicate=True),
            #             [Input('global-colorbar-store', 'data'),
            #                 # Input('points-attr', 'value')
            #                 ] +    
            #             [Input({'type': f'settings-{self.id}', 'key': x}, 'value') for x in self.settings.flat_keys])(update_render)
    
    


            def update_render(global_data, current_attr, *args):
                # 1. Update from Global Store (vmin, vmax, log)
                if global_data and current_attr in global_data:
                    config = global_data[current_attr]
                    for attr in ['vmin', 'vmax', 'log']:
                        if hasattr(self.settings, attr) and attr in config:
                            setattr(self.settings, attr, config[attr])

                # 2. Update all other settings from the UI
                # IMPORTANT: args must align 1:1 with flat_keys
                for key, arg in zip(self.settings.flat_keys, args):
                    # Handle Dash Color Picker dicts
                    if isinstance(arg, dict) and 'hex' in arg:
                        arg = arg['hex']
                    
                    if hasattr(self.settings, key):
                        # Get expected type from Pydantic/PanelSettings schema
                        prop_info = self.settings.schema['properties'].get(key, {})
                        prop_type = prop_info.get('type')
                        
                        try:
                            if prop_type == 'integer' and arg is not None:
                                # float conversion first handles cases like '20.0'
                                arg = int(float(arg)) 
                            elif prop_type == 'number' and arg is not None:
                                arg = float(arg)
                            elif prop_type == 'boolean':
                                # Handles string 'true' or actual boolean True
                                arg = (str(arg).lower() == 'true' or arg is True)
                            
                            # If type is None (common for Literals) or 'string', 
                            # we leave it as a string (e.g., 'longitude', '#ff0000')
                            setattr(self.settings, key, arg)
                            
                        except (ValueError, TypeError) as e:
                            print(f"Type Mismatch on {key}: cannot convert {arg} to {prop_type}")

                return self.render()

            # --- The Callback Definition ---
            # Crucial: The order of Inputs here MUST match the arguments above
            update_render = app.callback(
                Output(self.id, self.childname),
                [
                    Input('global-colorbar-store', 'data'), # Maps to global_data
                    Input('points-attr', 'value')            # Maps to current_attr
                ] + [
                    # These all map into the *args tuple
                    Input({'type': f'settings-{self.id}', 'key': x}, 'value') 
                    for x in self.settings.flat_keys
                ]
            )(update_render)


            
    def initialize(self):
        children = [dcc.Graph(figure=self.render(), id=self.id, mathjax=True, style={'height':'98%', 'width': '98%', 'align': 'center'})]
        if self.settings is not None:
            children.append(gear_maker(self.id))
        return html.Div(children,
                        style={'height': '100%'})

    def empty_render(self):
        fig = px.scatter(title='No data available', labels={'x': 'X-axis', 'y': 'Y-axis'})
        return fig

    def to_nodes(self):
        nodes = [dfl.Tab(id=f'tab-{self.id}', children=[self.initialize()])]
        if self.settings is not None:
            nodes.append(self.settings.node())
        return nodes
    
    @property
    def layout_dict(self):
        return {
            'type': 'tab',
            'id': f'tab-{self.id}',
            'name': f'{self.id.lower()}',
        }
     
    @property
    def output(self):
        return Output(self.id, self.childname, allow_duplicate=True)
        
        