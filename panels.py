import dash_bootstrap_components as dbc
from dash import Dash, html, Output, Input, dcc, State
from dash.exceptions import PreventUpdate

import dash_flexlayout as dfl

from dataclasses import dataclass
from dataclasses_jsonschema import JsonSchemaMixin

import tkinter as tk
from tkinter import filedialog

import plotly.express as px
import plotly.graph_objects as go
import numpy as np

# import dash_mantine_components as dmc

# gear = html.Div(html.Span([html.Img(id="logo", src="./assets/settings.svg", style={'height':'0.5cm'})],
#         style={'cursor': 'pointer'}), style={'textAlign': 'right'})  # Align content to the right


def gear_maker(id):
    gear = html.Div(
        html.Span(
            [html.Img(id=id+'_gear', src="./assets/settings.svg", style={'height': '0.5cm'})],
            style={'cursor': 'pointer', 'position': 'absolute', 'bottom': '0', 'right': '0'}
        ),
    )
    return gear

def search_dictionary(dic, id):
    stack = [(dic, 1)]
    max_depth = 1
    while stack:
        curr_dict, depth = stack.pop()
        for key, value in curr_dict.items():
            if isinstance(value, dict):
                stack.append((value, depth + 1))
            elif 'id' in key and value == id:
                    print(f"Found {id} at depth {depth} with key {key}")
        if depth > max_depth:
            print(f"New max depth: {depth} at key: {key}")
            print(stack)
        max_depth = max(max_depth, depth)
        
    return max_depth

# dic = {1:'a', 2: {3: {4: {}}}}
# print(dict_depth(dic))

def update_tabset(json_data, target_tab_id, settings_tab_id):
    # Traverse the layout to find the tabset containing the target tab
    # use a depth first search to find the tab

    # for key,value 


    

    for row in json_data['layout']['children']:
        for tabset in row['children']:
            if tabset['type'] == 'tabset':
                # Check if the target tab exists in this tabset
                for index, tab in enumerate(tabset['children']):
                    if tab['id'] == target_tab_id:
                        # Check if the settings tab exists
                        settings_tab_exists = any(t['id'] == settings_tab_id for t in tabset['children'])
                        
                        if not settings_tab_exists:
                            # Add the settings tab to the tabset
                            tabset['children'].append({
                                "type": "tab",
                                "id": settings_tab_id,
                                "name": "Settings",
                                "component": "text"
                            })
                        
                        # Find the index of the settings tab
                        for idx, t in enumerate(tabset['children']):
                            if t['id'] == settings_tab_id:
                                tabset['selected'] = idx  # Set the selected tab to the settings tab
                                break
                        
                        return json_data  # Return the updated JSON data
    return json_data

@dataclass
class PanelSettings:
    id: str
    _settings_schema: dict = None
    def __init__(self, id):
        self.id = id

    def initialize(self):
        # Main panel content (to be overridden by subclasses)
        return html.Div([html.H3(f"Panel: {self.id}")])

    def render(self):
        # Render settings form based on JSON schema
        if self.schema is None:
            return html.Div("No settings available.")
        form_items = [dcc.Markdown(f'# {self.id} settings')]
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
            # print(f"Settings clicked for {self.id}\tnClicks: {n_clicks}")
            if n_clicks:
                # Iterate through the layout to find the tabset containing the current tab
                print('depth of dictionary set: ', dict_depth(model))
                return update_tabset(model, f'tab-{self.id}', f'tab-{self.id}_settings')
                # str_model = str(model)
                # str_model=str_model.replace("\'selected\': 2", "\'selected\': 1")

                # return eval(str_model)
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


@dataclass
class MapSettings(PanelSettings):
    zoom: int = 14
    color: str = '#ff0000'


class Map(Panel):
    data: None

    def __init__(self, data, **kwargs):
        settings = MapSettings(id='map', **kwargs)
        super().__init__(id='map', settings=settings)
        self.data = data
        
    def render(self):
        fig = px.scatter_map(self.data, lat="latitude", lon="longitude", zoom=self.settings.zoom, color_discrete_sequence=[self.settings.color])
        fig.update_layout(map_style="white-bg",
            map_layers=[
                {
                    "below": 'traces',
                    "sourcetype": "raster",
                    "sourceattribution": "Google Earth (C)",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }])
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                          dragmode='select')
        return fig
        



@dataclass
class SoundingSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#0000ff'

class Sounding(Panel):
    lm_time: None
    lm_data: None
    hm_time: None
    hm_data: None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', SoundingSettings(id='sounding'))
        super().__init__(id='sounding', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        fig = go.Figure()
        # print(self.lm_data.ndim)
        lm_data = self.lm_data if self.lm_data.ndim > 1 else self.lm_data[np.newaxis,:]
        hm_data = self.hm_data if self.hm_data.ndim > 1 else self.hm_data[np.newaxis,:]
        # print(lm_data.shape)

        fig.add_trace(go.Scatter(x=self.lm_time, y=np.abs(lm_data[0]), mode='lines+markers', name='Low Moment',  line_color=self.settings.lm_color))
        fig.add_trace(go.Scatter(x=self.hm_time, y=np.abs(hm_data[0]), mode='lines+markers', name='High Moment', line_color=self.settings.hm_color))

        if lm_data.shape[0] > 1:
            for i in range(1, lm_data.shape[0]):
                fig.add_trace(go.Scatter(x=self.lm_time, y=np.abs(lm_data[i]), mode='lines+markers', showlegend=False, line_color=self.settings.lm_color))
                fig.add_trace(go.Scatter(x=self.hm_time, y=np.abs(hm_data[i]), mode='lines+markers', showlegend=False, line_color=self.settings.hm_color))
        
        fig.update_layout(
            xaxis_type="log",
            yaxis_type="log",
            xaxis_title="time [s]",
            yaxis_title="$\\frac{dB}{dt}$ [V / m$^2$]",
            margin=dict(t=30),
            dragmode='select'
        )
        return fig

@dataclass
class tTEMSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#2D81FF'
    lm_factor: float = 20.0
    hm_factor: float = 1.0

class tTEM(Panel):
    lm_time: None
    lm_data: None
    hm_time: None
    hm_data: None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', tTEMSettings(id='tTEM'))
        super().__init__(id='tTEM', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        fig = go.Figure()
        x_ttem = np.arange(len(self.hm_time))
        for i_row in range(len(self.lm_time[0])):
            fig.add_trace(go.Scatter(x=x_ttem, y=self.settings.lm_factor*np.abs(self.lm_data[:, i_row]), mode='lines+markers', name=f'Low Moment {i_row}', showlegend=False, line_color=self.settings.lm_color))
        for i_row in range(len(self.hm_time[0])):
            fig.add_trace(go.Scatter(x=x_ttem, y=self.settings.hm_factor*np.abs(self.hm_data[:, i_row]), mode='lines+markers', name=f'High Moment {i_row}', showlegend=False, line_color=self.settings.hm_color))
        fig.update_layout(
            yaxis_type="log",
            xaxis_title="data index",
            yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
            margin=dict(t=30),
            dragmode='select'
        )
        return fig    

if __name__ == '__main__':
    import dash_mantine_components as dmc

    app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')



    from dash import dcc
    import example_panels as ep
    m1 = Map(data=ep.df)
    dbdt1 = Sounding(lm_time=ep.lm.time.mean(0),
                     lm_data=ep.lm.data.mean(0),
                     hm_time=ep.hm.time.mean(0),
                     hm_data=ep.hm.data.mean(0))

    tTEM1 = tTEM(lm_time=ep.lm.time,
                lm_data=ep.lm.data,
                hm_time=ep.hm.time,
                hm_data=ep.hm.data)

    nodes = m1.to_nodes() + dbdt1.to_nodes() + tTEM1.to_nodes()

    config = {
        "global": {"tabEnableClose": True, "tabEnableFloat": True},
        "borders": [
            {"type": "border", "location": "right", "size": 200, "children": [                    
                        {
                            "type": "tab",
                            "name": "One",
                            "component": "text",
                            "id": "side-1",
                            "tabEnableClose": False,
                        },
            ]},
        ],
        "layout": {
            "type": "row",
            "weight": 100,
            "children": [{
                    "type": "tabset",
                    "weight": 50,
                    "selected": 1,
                    "children": [
                        m1.layout_dict,
                        m1.settings.layout_dict,
                    ],
                },
                {
                    "type": "tabset",
                    "weight": 50,
                    "selected": 1,
                    "children": [
                        dbdt1.layout_dict,
                        tTEM1.layout_dict,
                    ],
                },
            ],
        },
    }

    app.layout = html.Div([
        dcc.Location(id='url', refresh=False),
        dfl.FlexLayout(
        id="flex-layout",
        model=config,
        children=nodes,
        useStateForModel=False,
        
    )]
    )

    m1.add_callbacks(app)
    dbdt1.add_callbacks(app)
    tTEM1.add_callbacks(app)

    @app.callback(
        [Output('sounding', 'figure', allow_duplicate=True),
                Output('tTEM', 'figure', allow_duplicate=True)],
        Input('map', 'selectedData'),
        prevent_initial_call="initial_duplicate",
        allow_duplicate=True
    )
    def update_dbdt(selected_data):
        if not selected_data or 'points' not in selected_data:
            raise PreventUpdate

        # Extract selected points
        selected_points = [point['pointIndex'] for point in selected_data['points']]

        dbdt1.hm_data = ep.hm.data[selected_points]*1.
        dbdt1.lm_data = ep.lm.data[selected_points]*1.

        tTEM1.hm_data = ep.hm.data[selected_points]*1.
        tTEM1.lm_data = ep.lm.data[selected_points]*1.
        tTEM1.hm_time = ep.hm.time[selected_points]*1.
        tTEM1.lm_time = ep.lm.time[selected_points]*1.
        return dbdt1.render(), tTEM1.render()



    app.run(debug=True, port=8050, dev_tools_hot_reload=True)