from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table
import numpy as np

import plotly.io as pio

# Define a custom template
custom_template = {
    "layout": {
        "font": {"family": "Arial", "size": 14, "color": "black"},
        "plot_bgcolor": "white",
        "paper_bgcolor": "white",
        "margin": {"l": 50, "r": 50, "t": 50, "b": 50},
        "xaxis": {
            "showgrid": True,
            "gridcolor": "#e5e5e5",
            "zeroline": False,
            "showline": True,
            "linecolor": "black",
            "ticks": "outside",
        },
        "yaxis": {
            "showgrid": True,
            "gridcolor": "#e5e5e5",
            "zeroline": False,
            "showline": True,
            "linecolor": "black",
            "ticks": "outside",
        },
    }
}

# Register the custom template
pio.templates["custom"] = custom_template

# Set the custom template as the default
pio.templates.default = "custom"

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

    def initialize(self):
        return html.Div([dcc.Graph(figure=self.render(), id=self.id, mathjax=True, 
                                   style={'height': '100%'}),
                         gear_maker(self.id)],
                        style={'height': '100%', 'overflow': 'hidden'} )
        



@dataclass
class dbdtSoundingSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#0000ff'
    plot_error: bool = False

class dbdtSounding(Panel):
    dataframe = None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSoundingSettings(id='sounding'))
        super().__init__(id='sounding', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        df_tmp = self.dataframe#.copy()
        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto'] = False

        
        fig = px.line(
            df_tmp,
            x='time',
            y="dbdt",
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            markers=True,
            title="dbdt vs time by site_id",
            custom_data=["gate_id", "data_id"],
            hover_data=["data_id"],
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto'] = True
        df_tmp.loc[(~df_tmp['inuse_auto']), 'dbdt'] = np.nan
        fig2 = px.line(
            df_tmp,
            x='time',
            y="dbdt",
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            markers=True,
            title="dbdt vs time by site_id",
        )


        for trace in fig2.data:
            fig.add_trace(trace)

        fig.update_layout(
            xaxis_type="log",
            yaxis_type="log",
            xaxis_title='time [s]',
            yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
            margin={"l": 50, "r": 50, "t": 50, "b": 50},
            dragmode='select'
        )
        return fig    

class rhoaSounding(Panel):
    lm_time: None
    lm_data: None
    hm_time: None
    hm_data: None

    @staticmethod
    def to_rhoa(time, dbdt, area=1., current=1.):
        from numpy import pi
        mu0 = 4 * pi * 1e-7
        if dbdt.ndim > time.ndim:
            t = time[np.newaxis, :]
        else:
            t = time

        rho_a = ((current*area)**(2/3) * (mu0**(5/3))) / ((20 * dbdt)**(2/3) * (pi**(1/3)) * time**(5/3))
        return rho_a


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSoundingSettings(id='rhoa'))
        super().__init__(id='rhoa', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        fig = go.Figure()
        # print(self.lm_data.ndim)
        lm_data = self.lm_data if self.lm_data.ndim > 1 else self.lm_data[np.newaxis,:]
        hm_data = self.hm_data if self.hm_data.ndim > 1 else self.hm_data[np.newaxis,:]

        lm_data = rhoaSounding.to_rhoa(self.lm_time*1., np.abs(lm_data))
        hm_data = rhoaSounding.to_rhoa(self.hm_time*1., np.abs(hm_data))

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
            margin={"l": 50, "r": 50, "t": 50, "b": 50},
            dragmode='select'
        )
        return fig


from typing import Literal
@dataclass
class dbdtSectionSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#2D81FF'
    lm_factor: float = 20.0
    hm_factor: float = 1.0
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude'] = 'daytime'  # or 'site_id', 'longitude', 'latitude'
    y_axis: str = 'dbdt_syn'
    plot_disabled: bool = True

class dbdtSection(Panel):
    dataframe = None

    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSectionSettings(id='tTEM'))
        super().__init__(id='tTEM', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def compare_synthetic(self):
        y_axis                                             = 'dbdt_syn'
        df_tmp                                             = self.dataframe.sort_values(['gate_id', self.settings.x_axis])
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt_syn']  *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt_syn']  *= self.settings.hm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto']  = False
        df_tmp['system_id']                                = df_tmp['system_id'].map({0: 'hm', 1: 'lm'})

        error_ub,error_lb = 'error_ub', 'error_lb'
        if True:
            error_ub = None
            error_lb = None
        
        fig = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id"],
            error_y=error_ub,
            error_y_minus=error_lb
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto'] = True
        df_tmp.loc[(~df_tmp['inuse_auto']), 'dbdt'] = np.nan
        df_tmp.loc[(~df_tmp['inuse_auto']), 'dbdt_syn'] = np.nan


        
        fig3 = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color_discrete_sequence=["black", "black"],
            color="system_id",
            title="dbdt vs time by site_id",
            # custom_data=["system_id", "data_id"],
            error_y=error_ub,
            error_y_minus=error_lb,
        )

        fig2 = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt_syn',
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)

        return fig    

    def standard_render(self):
        y_axis = 'dbdt'

        df_tmp = self.dataframe.sort_values(['gate_id', self.settings.x_axis])
        df_tmp.loc[df_tmp['system_id'] == 'lm', y_axis] *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 'hm', y_axis] *= self.settings.hm_factor


        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto'] = False

        
        fig = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y=y_axis,
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            markers=True,
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id"],

        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'inuse_auto'] = True
        df_tmp.loc[(~df_tmp['inuse_auto']), y_axis] = np.nan
        fig2 = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y=y_axis,
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            markers=True,
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id"],
        )


        for trace in fig2.data:
            fig.add_trace(trace)    
        return fig    

    def render(self):
        fig = self.compare_synthetic()
        # fig = self.standard_render()

        fig.update_layout(
            yaxis_type="log",
            xaxis_title=self.settings.x_axis,
            yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
            margin={"l": 50, "r": 50, "t": 50, "b": 50},
            dragmode='select'
        )
        return fig    


@dataclass
class AutoProcessing(PanelSettings):
    sign_correction:  bool = False
    remove_negatives: bool = False


class Upload(Panel):
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', AutoProcessing(id='upload', title='Auto Processing Settings'))
        super().__init__(id='upload', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def render(self):
        return html.Div(
            [
                dcc.Upload(
                    id='upload-data',
                    children=html.Div([
                        'Drag and Drop \n or \n',
                        html.A('Select Files')
                    ], style={'height': '110px', 'lineHeight': '100px', 'textAlign': 'center'}),
                    style={
                        'borderWidth': '2px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                    },
                    multiple=True,
                ),
                html.Div(id='output-data-upload'),
        ],
        )
    
    def initialize(self):
        return html.Div([
            dcc.Markdown("# welcome to sea anemone", style={'textAlign': 'center'}),
            dcc.Markdown("Upload your data to get started."),
            self.render(),
            gear_maker(self.id)],
            style={'margin':'10px'}#,'height': 'calc(100%-30px)', 'overflow': 'hidden'} 
        )


@dataclass
class TableSettings(PanelSettings):
    max_rows: int = 6
    visible_columns: list[bool] = None

    def special_renders(self):
        special_renders = super().special_renders()
        vis_check = lambda key,prop: key == 'visible_columns'
        def vis_render(key, prop):
            checkbox_row = []
            if hasattr(self, 'column_names'):
                col_names = self.column_names
            else:
                col_names = [str(i) for i in range(self.visible_columns_len)]

            for i, (val, name) in enumerate(zip(self.visible_columns, col_names)):
                checkbox_row.append(
                    html.Div([
                        html.Label(name, style={'fontSize': '12px', 'marginLeft': '5px'}),
                        dbc.Checkbox(
                            id={'type': f'settings-{self.id}', 'key': f'{key}-{i}'},
                            #value=self.visible_columns[i] if i < len(self.visible_columns) else True,
                            value=val,
                            style={'margin': '5px', 'horizontalAlign': 'center', 'verticalAlign': 'middle'}
                        ),
                    ], style={'display': 'inline-block', 'marginRight': '15px', 'verticalAlign': 'top'})
                )
            
            return html.Div([
                html.Br(),
                html.Div(checkbox_row, style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px'}),
                html.Br()])
        
        special_renders.append((vis_check, vis_render))
        return special_renders
    
class Table(Panel):
    def __init__(self, dataframe, **kwargs):
        id = kwargs.pop('id', 'table')
        settings = kwargs.pop('settings', TableSettings(id, visible_columns=[True for _ in dataframe.columns.tolist()]))
        settings.column_names = dataframe.columns.tolist()
        super().__init__(id=id, settings=settings, childname='children')
        self.df = dataframe
        self.dashtable = None

        for key, value in kwargs.items():
            setattr(self, key, value)      

    def render(self):
        # if self.dashtable is None:
        self.dashtable = dash_table.DataTable(
            data=self.df.to_dict('records'),
            columns=[{"name": i, "id": i} for i in self.df.columns[self.settings.visible_columns]],
            page_size=self.settings.max_rows,
            sort_action="native",
            style_table={'height': '400px', 'overflowY': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '5px', 'fontSize': '12px'},
            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
        )
        # self.dashtable.SelectedCells = self.dashtable.SelectedCells if hasattr(self.dashtable, 'SelectedCells') else None
        return html.Div(self.dashtable)
                
    def initialize(self):
        if hasattr(self, 'name'):
            name = self.name
        else:
            name = self.id
        return html.Div([
            dcc.Markdown(f"## {name}"),
            self.render(),
            gear_maker(self.id)],
            style={'margin':'10px'}#,'height': 'calc(100%-30px)', 'overflow': 'hidden'} 
        )

import pandas as pd
@dataclass
class ModelGraphSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    color_by: Literal['site_id', 'misfit'] = 'site_id'

class ModelGraph(Panel):
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelGraphSettings(id='model_graph'))
        super().__init__(id='model_graph', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        # ...existing code...
        df_layers_long = pd.melt(
            self.dataframe,
            id_vars=['site_id', 'daytime', 'longitude', 'latitude', 'date', 'elevation', 'layer', 'resistivity'],
            value_vars=['top_depth', 'bottom_depth'],
            var_name='depth_type',
            value_name='depth'
        ).sort_values(['daytime', 'layer', 'depth'])

        df_layers_long = df_layers_long.drop(columns=['depth_type'])

        fig = px.line(
            df_layers_long,
            x="resistivity",
            y="depth",
            color="site_id",
            # markers=True,
            labels={
                "resistivity": "Resistivity [Ω·m]",
                "center_depth": "Depth [m]",
                "site_id": "Site ID"
            },
            title="Resistivity vs. Depth by Site"
        )

        # Reverse y-axis so depth increases downward
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(
            xaxis_type="log",
        )
        return fig        
    
@dataclass
class ModelSectionSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude'] = 'daytime'

class ModelSection(Panel):
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelSectionSettings(id='model_section'))
        super().__init__(id='model_section', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        # ...existing code...
        df_layers_long = pd.melt(
            self.dataframe,
            id_vars=['site_id', 'daytime', 'longitude', 'latitude', 'date', 'elevation', 'layer', 'resistivity'],
            value_vars=['top_depth', 'bottom_depth'],
            var_name='depth_type',
            value_name='depth'
        ).sort_values(['daytime', 'layer', 'depth'])

        df_layers_long = df_layers_long.drop(columns=['depth_type'])
        df_layers_long['log_resistivity'] = np.log10(df_layers_long['resistivity'])

        heatmap_df = df_layers_long.pivot_table(
            index='depth', columns=self.settings.x_axis, values='log_resistivity'
        )        
        heatmap_df = heatmap_df.sort_index(ascending=True)

        fig = px.imshow(
            heatmap_df,
            aspect='auto',
            origin='lower',
            color_continuous_scale='turbo',
            labels={'x': self.settings.x_axis, 'y': 'Depth [m]', 'color': 'Resistivity [Ω·m]'},
            title='Resistivity Heatmap by Site and Depth',
            zmin=heatmap_df.min().min(),
            zmax=heatmap_df.max().max(),
        )

        fig.update_yaxes(autorange="reversed")
        return fig



if __name__ == '__main__':
    import dash_mantine_components as dmc
    from dash import Dash
    app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')



    from dash import dcc
    import example_panels as ep
    m1 = Map(data=ep.df)
    dbdt1 = dbdtSounding(lm_time=ep.lm.time.mean(0),
                     lm_data=ep.lm.data.mean(0),
                     hm_time=ep.hm.time.mean(0),
                     hm_data=ep.hm.data.mean(0))
    
    rhoa1 = rhoaSounding(lm_time=ep.lm.time.mean(0),
                     lm_data=ep.lm.data.mean(0),
                        hm_time=ep.hm.time.mean(0),
                        hm_data=ep.hm.data.mean(0))
    

    dbdt2 = dbdtSection(lm_time=ep.lm.time,
                lm_data=ep.lm.data,
                hm_time=ep.hm.time,
                hm_data=ep.hm.data)
    u1 = Upload()
    t1 = Table(dataframe=ep.df, id='overview table')

    panels = [u1, m1, dbdt1, dbdt2, rhoa1, t1]
    nodes = [node for panel in panels for node in panel.to_nodes()]
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
                    "children": [
                        t1.layout_dict,
                        m1.layout_dict,
                        u1.layout_dict,
                    ],
                },
                {
                    "type": "tabset",
                    "weight": 50,
                    "children": [
                        dbdt1.layout_dict,
                        dbdt2.layout_dict,
                        rhoa1.layout_dict,
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
    
    for panel in panels:
        panel.add_callbacks(app)

    @app.callback(
        [ 
            Output('sounding', 'figure', allow_duplicate=True),
            Output('tTEM',     'figure', allow_duplicate=True),
            Output('rhoa',     'figure', allow_duplicate=True)
        ],
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
        
        rhoa1.hm_data = ep.hm.data[selected_points]*1.
        rhoa1.lm_data = ep.lm.data[selected_points]*1.        

        dbdt2.hm_data = ep.hm.data[selected_points]*1.
        dbdt2.lm_data = ep.lm.data[selected_points]*1.
        dbdt2.hm_time = ep.hm.time[selected_points]*1.
        dbdt2.lm_time = ep.lm.time[selected_points]*1.
        return dbdt1.render(), dbdt2.render(), rhoa1.render()
    app.run(debug=True, port=8050, dev_tools_hot_reload=True)