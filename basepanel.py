import dash_bootstrap_components as dbc
from dash import  html, Output, Input, dcc, State
from dash.exceptions import PreventUpdate

import dash_flexlayout as dfl

from dataclasses import dataclass
from dataclasses_jsonschema import JsonSchemaMixin

import tkinter as tk
from tkinter import filedialog

import plotly.express as px
import plotly.graph_objects as go
import numpy as np


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


@dataclass
class PanelSettings:
    id: str
    _settings_schema: dict = None
    title: str = None
    def __init__(self, id):
        self.id = id

    def initialize(self):
        # Main panel content (to be overridden by subclasses)
        return html.Div([html.H3(f"Panel: {self.id}")])

    def render(self):
        # Render settings form based on JSON schema
        if self.schema is None:
            return html.Div("No settings available.")
        form_items = [dcc.Markdown(f'# {self.id} settings') if self.title is None else dcc.Markdown(f'# {self.title}')]
        for key, prop in self.schema.get('properties', {}).items():
            row_children = []
            row_children.append(dbc.Label(prop.get('title', key), style={'marginRight': '10px'}))
            if 'color' in key.lower():
                import dash_daq as daq
                row_children.append(
                    daq.ColorPicker(
                        id={'type': f'settings-{self.id}', 'key': key},
                        label=key.lower(),
                        value={'hex': eval(f'self.{key}')},
                        size=164,
                        style={'margin': '5px'}
                    )
                )
            elif 'enum' in prop:
                row_children.append(
                    dbc.Select(
                        options=[{"label": v, "value": v} for v in prop['enum']],
                        id={'type': f'settings-{self.id}', 'key': key},
                        value=eval(f'self.{key}'),
                        style={'margin': '5px'}
                    )
                )
            else:
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
                         gear_maker(self.id+'_settings')])

    def node(self):
        return dfl.Tab(id=f'tab-{self.id}_settings', children=[self.render()])
    
    @classmethod
    def _create_schema(cls):
        class tmp(cls, JsonSchemaMixin):
            pass
        return tmp.json_schema()
    
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
                root.attributes('-topmost',True)
                
                fname = filedialog.asksaveasfilename(
                    title="Save Settings",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
                    initialfile=f"{self.id}_settings.json"
                )

                self.save_settings(fname)
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
                root.attributes('-topmost',True)
                fname = filedialog.askopenfilename(
                    title="Load Settings",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                if fname:
                    self.load_settings(fname)
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
                return update_tabset(model, f'tab-{self.id}_settings', f'tab-{self.id}', change_order=False)
            else:
                raise PreventUpdate                

@dataclass
class Panel:
    id: str
    settings: PanelSettings = None

    def add_callbacks(self, app):
        self.settings.add_callbacks(app)
        def update_render(*args):
            for key, arg in zip(self.settings.schema.get('properties', {}).keys(), args):
                if isinstance(arg, dict) and 'hex' in arg:
                    arg = arg['hex']
                
                if hasattr(self.settings, key):
                    setattr(self.settings, key, arg)
    
            return self.render()
        
        update_render = app.callback(Output(self.id, 'figure'),
                    [Input({'type': f'settings-{self.id}', 'key': x}, 'value') for x in self.settings.schema.get('properties', {}).keys()])(update_render)
    
    
    def initialize(self):
        return html.Div([dcc.Graph(figure=self.render(), id=self.id, mathjax=True, style={'height': '100%'}),
                         gear_maker(self.id)],
                        style={'height': '100%', 'overflow': 'hidden'} )
                         
    
    def to_nodes(self):
        # Returns a layout with panel and settings tab
        return [dfl.Tab(id=f'tab-{self.id}', children=[self.initialize()]), self.settings.node()]
    
    @property
    def layout_dict(self):
        return {
            'type': 'tab',
            'id': f'tab-{self.id}',
            'name': f'{self.id.lower()}',
        }