import dash
from dash import html, dcc
import dash_bootstrap_components as dbc
import plotly.express as px

def create(df, id='map'):
    from plotly.express import scatter_map
    from dash.dcc import Graph

    map = scatter_map(df, lat="latitude", lon="longitude", zoom=14,  color_discrete_sequence=['red'])
    map.update_layout(map_style="white-bg",
        map_layers=[
            {
                "below": 'traces',
                "sourcetype": "raster",
                "sourceattribution": "Google Earth (C)",
                "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
            }])
    map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
    return Graph(figure=map, id=id)


from dataclasses import dataclass
from dataclasses_jsonschema import JsonSchemaMixin
import dash_flexlayout as dfl
import tkinter as tk
from tkinter import filedialog


@dataclass
class Panel:
    _settings_schema: dict = None
    def __init__(self, id, data=None):
        self.id = id
        self.data = data

    def initialize(self):
        # Main panel content (to be overridden by subclasses)
        return html.Div([html.H3(f"Panel: {self.id}")])

    def render_settings(self):
        # Render settings form based on JSON schema
        if self.schema is None:
            return html.Div("No settings available.")
        form_items = [dcc.Markdown(f'# {self.id} settings')]
        for key, prop in self.schema.get('properties', {}).items():
            row_children = []
            row_children.append(dbc.Label(prop.get('title', key), style={'marginRight': '10px'}))
            if key.lower() == 'color' or 'color' in prop.get('title', '').lower():
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

        return dbc.Form(form_items, style={'margin': '10px'})

    def to_nodes(self):
        return [
            dfl.Tab(id=f'tab-{self.id}', children=[self.initialize()]),
            dfl.Tab(id=f'tab-{self.id}_settings', children=[self.render_settings()])
        ]
    
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
            self._settings_schema = tmp
        return self._settings_schema
    
    @property
    def settings(self):
        return {k: getattr(self, k) for k in self.schema.get('properties', {}).keys() if hasattr(self, k)}
    
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

    def add_settings_callbacks(self, app):
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
            
            return self.render_settings()


if __name__ == '__main__':

    @dataclass
    class MapPanel(Panel): 
        zoom           : int  = 14
        color          : str = '#ff0000'

        def __init__(self, data, **kwargs):
            super().__init__(id='map', data=data)
            for key, value in kwargs.items():
                setattr(self, key, value)
            

        def render(self):
            fig = px.scatter_map(self.data, lat="latitude", lon="longitude", zoom=self.zoom, color_discrete_sequence=[self.color])
            fig.update_layout(map_style="white-bg",
                map_layers=[
                    {
                        "below": 'traces',
                        "sourcetype": "raster",
                        "sourceattribution": "Google Earth (C)",
                        "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                    }])
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
            return fig
        
        def initialize(self):
            return dcc.Graph(figure=self.render(), id=self.id)


        def add_callbacks(self, app):
            self.add_settings_callbacks(app)

            def update_map(*args):
                self.zoom = args[0]
                self.color = args[1]['hex']

                return self.render()


            update_map = app.callback(Output(self.id, 'figure'),
                        [Input({'type': f'settings-{self.id}', 'key': x}, 'value') for x in self.schema.get('properties', {}).keys()])(update_map)


    import dash
    from dash import Dash, html, Output, Input, State
    from dash.exceptions import PreventUpdate
    import dash_mantine_components as dmc

    import dash_flexlayout as dfl

    app = dash.Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')

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
                        {
                            "type":"tab",
                            "name": "Two",
                            "component": "text",
                            "id": "tab-panels",
                            "tabEnableClose": False,
                        },
                        {
                            "type":"tab",
                            "name": "Two1",
                            "component": "text",
                            "id": "tab-dump",
                            "tabEnableClose": False,
                        }
                        
                        ]},
        ],
        "layout": {
            "type": "row",
            "weight": 100,
            "children": [
                {
                    "type": "tabset",
                    "weight": 100,
                    "selected": 0,
                    "children": [
                        {
                            "type": "tab",
                            "name": "Three",
                            "component": "text",
                            "enableFloat": True,
                            "id": "tab-map",
                        },
                        {
                            "type": "tab",
                            "name": "Three1",
                            "component": "text",
                            "enableFloat": True,
                            "id": "tab-map_settings",
                        },

                    ],
                }],
        },
    }

    from dash import dcc
    import example_panels as ep
    m1 = MapPanel(data=ep.df)

    nodes = m1.to_nodes()

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

    app.run(debug=True, port=8050, dev_tools_hot_reload=True, dev_tools_ui=True)
        