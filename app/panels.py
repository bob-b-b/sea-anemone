from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table
import numpy as np

import plotly.io as pio

from typing import Literal
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import os

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
    highlight_color: str= '#ffff00'  # Default highlight color



class Map(Panel):
    dataframe: None
    highlighted: int = None

    def __init__(self, data, **kwargs):
        settings = MapSettings(id='map', **kwargs)
        super().__init__(id='map', settings=settings)
        self.dataframe = data

    def render(self):
        if self.dataframe is None: return self.empty_render()

        fig = px.scatter_map(self.dataframe, lat="latitude", lon="longitude", zoom=self.settings.zoom, color_discrete_sequence=[self.settings.color])
        fig.update_layout(map_style="white-bg",
            map_layers=[
                {
                    "below": 'traces',
                    "sourcetype": "raster",
                    "sourceattribution": "Google Earth (C)",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }])
        if self.highlighted is not None:
            highlight_trace = px.scatter_map(self.dataframe[self.dataframe.index == self.highlighted], lat="latitude", lon="longitude", color_discrete_sequence=[self.settings.highlight_color])
            highlight_trace.update_traces(marker=dict(size=14))
            for trace in highlight_trace.data:
                fig.add_trace(
                    trace
                )
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                          modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
                          newshape=dict(line_color='cyan', line_width=3),
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
    lm_factor: float = 20.0
    hm_factor: float = 1.0
    plot_error: bool = False
    x_axis: Literal['time', 'gate_id'] = 'time'  # or 'site_id', 'longitude', 'latitude'

class dbdtSounding(Panel):
    dataframe = None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSoundingSettings(id='sounding'))
        super().__init__(id='sounding', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)

    def compare_synthetic(self):

        y_axis                                             = 'dbdt_syn'

        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto'])
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt_syn']  *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt_syn']  *= self.settings.hm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] == -1, 'include']  = False

        df_tmp['system_id']                                = df_tmp['system_id'].map({1: 'hm', 0: 'lm'})

        error_ub,error_lb = 'error_ub', 'error_lb'
        # if True:
        #     error_ub = None
        #     error_lb = None
        
        fig = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            title="Sounding curve",
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'include'] = True
        df_tmp.loc[(~df_tmp['include']), 'dbdt']       = np.nan
        df_tmp.loc[(~df_tmp['include']), 'dbdt_syn']   = np.nan


        
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
            custom_data=["system_id", "data_id", "site_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)

        return fig    

    def observed_only(self):

        y_axis                                             = 'dbdt_syn'
        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto']).astype(bool)
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] == -1, 'include']  = False

        df_tmp['system_id']                                = df_tmp['system_id'].map({1: 'hm', 0: 'lm'})

        error_ub,error_lb = 'error_ub', 'error_lb'
        # if True:
        #     error_ub = None
        #     error_lb = None
        
        fig = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            title="Sounding curve",
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'include'] = True
        df_tmp.loc[(~df_tmp['include']), 'dbdt'] = np.nan


        
        fig2 = px.scatter(
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

        fig3 = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id", "site_id"],
        )
        
        for trace in fig2.data:
            fig.add_trace(trace)

        for trace in fig3.data:
            fig.add_trace(trace)



        return fig     

    def render(self):
        if self.dataframe is None: return self.empty_render()


        if 'dbdt_syn' in self.dataframe.columns:
            fig = self.compare_synthetic()
        else:
            fig = self.observed_only()

        fig.update_layout(
            yaxis_type="log",
            xaxis_type="log" if self.settings.x_axis == 'time' else "linear",
            xaxis_title=self.settings.x_axis,
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
        if self.dataframe is None: return self.empty_render()
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


@dataclass
class dbdtSectionSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#2D81FF'
    lm_factor: float = 20.0
    hm_factor: float = 1.0
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude', 'distance'] = 'site_id'#, 'longitude', 'latitude'
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
        y_axis                                             = self.settings.y_axis
        df_tmp = self.dataframe[self.dataframe['gate_id']>-1]
        df_tmp                                             = df_tmp.sort_values(['gate_id', self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto'])

        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt_syn']  *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt_syn']  *= self.settings.hm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] ==  -1, 'include']  = False
        df_tmp['system_id']                                = df_tmp['system_id'].map({0: 'hm', 1: 'lm'})

        x_axis = df_tmp[self.settings.x_axis].unique()#.values
        if self.settings.x_axis == 'site_id':
            x_axis = x_axis[x_axis>-1]
        xmin,xmax = np.nanmin(x_axis), np.nanmax(x_axis)

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
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'include'] = True
        df_tmp.loc[(~df_tmp['include']), 'dbdt'] = np.nan
        df_tmp.loc[(~df_tmp['include']), 'dbdt_syn'] = np.nan

        
        
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
            title="field data versus simulated data",
            custom_data=["system_id", "data_id", "site_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)
        dx = xmax - xmin
        fig.update_xaxes(range=[xmin-0.1*dx, xmax+0.1*dx])
        return fig    

    def observed_only(self):
        y_axis                                             = self.settings.y_axis
        df_tmp = self.dataframe[self.dataframe['gate_id']>-1]
        df_tmp                                             = df_tmp.sort_values(['gate_id', self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto']).astype(bool)
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] ==  -1, 'include']  = False
        df_tmp['system_id']                                = df_tmp['system_id'].map({0: 'hm', 1: 'lm'})

        x_axis = df_tmp[self.settings.x_axis].unique()#.values
        if self.settings.x_axis == 'site_id':
            x_axis = x_axis[x_axis>-1]
        xmin,xmax = np.nanmin(x_axis), np.nanmax(x_axis)


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
            title="Manual processing",
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb,
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'include'] = True
        df_tmp.loc[(~df_tmp['include']), 'dbdt'] = np.nan
        
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
            y='dbdt',
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id", "site_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)
        dx = xmax - xmin
        
        fig.update_xaxes(range=[xmin-0.1*dx, xmax+0.1*dx])
        
        return fig  

    def render(self):
        if self.dataframe is None: return self.empty_render()
        if 'dbdt_syn' in self.dataframe.columns:
            fig = self.compare_synthetic()
        else:
            fig = self.observed_only()

        fig.update_layout(
            yaxis_type="log",
            xaxis_title=self.settings.x_axis,
            yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
            margin={"l": 50, "r": 50, "t": 50, "b": 50},
            dragmode='select'
        )
        return fig    

markdown_text = '''
# Panels
## Data
- [Sounding](#sounding)     [[+]](#new_sounding)
- [Section](#section)       [[+]](#new_section)
## Models
- [graph](#graph)           [[+]](#new_graph)
- [colorbar](#colorbar)     [[+]](#new_colorbar)
- [table](#table)           [[+]](#new_table)
'''

panel_list = html.Div([
    dcc.Markdown(children=markdown_text)
])

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
        session_text = "### Recent sessions\n"
        if self.session_files is not None:
            for f in self.session_files:
                session_text += f"- [{f}](#load={f})\n"
        else:
            session_text += "No recent sessions found."
        return html.Div([
            dcc.Markdown("# Welcome to sea anemone", style={'textAlign': 'center'}),
            dcc.Markdown("### Upload your data to get started."),
            self.render(),
            dcc.Markdown("---"),
            dcc.Markdown(session_text),
            gear_maker(self.id)],
            style={'margin':'10px'}#,'height': 'calc(100%-30px)', 'overflow': 'hidden'} 
        )


@dataclass
class TableSettings(PanelSettings):
    max_rows: int = 50
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
        self.dataframe = dataframe
        self.dashtable = None

        for key, value in kwargs.items():
            setattr(self, key, value)      

    def render(self):
        # colums = 
        self.dashtable = dash_table.DataTable(
            data=self.dataframe.to_dict('records'),
            columns=[{"name": name, "id": name} for i,name in enumerate(self.dataframe.columns) if self.settings.visible_columns[i]],
            page_size=self.settings.max_rows,
            sort_action="native",
            style_table={'height': '400px', 'overflowY': 'auto'},
            style_cell={'textAlign': 'left', 'padding': '5px', 'fontSize': '12px'},
            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
        )
        # self.dashtable.SelectedCells = self.dashtable.SelectedCells if hasattr(self.dashtable, 'SelectedCells') else None
        return html.Div(self.dashtable, id=self.id)
                
    def initialize(self):
        if hasattr(self, 'name'):
            name = self.name
        else:
            name = self.id
        return html.Div([
            self.render(),
            gear_maker(self.id)],
            style={'margin':'10px'}#,'height': 'calc(100%-30px)', 'overflow': 'hidden'} 
        )

import pandas as pd
@dataclass
class ModelGraphSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    color_by: Literal['site_id', 'misfit'] = 'site_id'
    rho_min: float = 1.0
    rho_max: float = 1000.0

class ModelGraph(Panel):
    highlighted=None
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelGraphSettings(id='model_graph'))
        super().__init__(id='model_graph', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        if self.dataframe is None: return self.empty_render()
        # ...existing code...
        df_layers_long = pd.melt(
            self.dataframe,
            id_vars=['site_id', 'daytime', 'longitude', 'latitude', 'date', 'elevation', 'layer', 'resistivity'],
            value_vars=['top_depth', 'bottom_depth'],
            var_name='depth_type',
            value_name='depth'
        ).sort_values(['site_id', 'daytime', 'layer', 'depth'])

        df_layers_long = df_layers_long.drop(columns=['depth_type'])
        df_above = df_layers_long[df_layers_long["depth"] <= df_layers_long["doi_depth"]]
        df_below = df_layers_long[df_layers_long["depth"] >  df_layers_long["doi_depth"]]

        if self.highlighted is None:
            fig = px.line(
                df_layers_long,
                x="resistivity",
                y="depth",
                color="site_id",
                labels={
                    "resistivity": "ρ [Ω·m]",  # Unicode rho
                    "site_id": "Site ID"
                },
                title="Resistivity vs. Depth by Site"
            )
        else:
            fig = go.Figure()
            df_highlighted = df_layers_long[df_layers_long['site_id'] == self.highlighted]
            fig.add_trace(
                go.Scatter(
                    x=df_highlighted["resistivity"],
                    y=df_highlighted["depth"],
                    mode="lines",
                    line=dict(width=2, color='red'),
                    zorder=10,
                    name=f"Site {self.highlighted}"
                ), 
            )
            fig.add_trace(
                go.Scatter(
                    x=df_layers_long["resistivity"],
                    y=df_layers_long["depth"],
                    mode="lines",
                    line=dict(color='gray'),
                    name='All Sites'
                ), 
            )



        # Reverse y-axis so depth increases downward
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(type="log", range=[np.log10(self.settings.rho_min), np.log10(self.settings.rho_max)])
        return fig        
    
@dataclass
class ModelSectionSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude', 'distance'] = 'daytime'

class ModelSection(Panel):
    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', ModelSectionSettings(id='model_section'))
        super().__init__(id='model_section', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    def render(self):
        if self.dataframe is None: return self.empty_render()
        df_layers_long = self.dataframe.melt(
            id_vars=['site_id', 'daytime', 'longitude', 'latitude', 'date', 'elevation', 'layer', 'resistivity', 'misfit','doi'],
            value_vars=['top_depth', 'bottom_depth'],
            var_name='depth_type',
            value_name='depth'
        ).sort_values(['daytime', 'layer', 'depth'])

        df_layers_long = df_layers_long.drop(columns=['depth_type'])
        df_layers_long['log_resistivity'] = np.log10(df_layers_long['resistivity'])
        df_layers_long["below_doi"] = (df_layers_long["depth"] > df_layers_long["doi"])

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
            title='Resistivity',
            zmin=heatmap_df.min().min(),
            zmax=heatmap_df.max().max(),
        )
        fig.update_layout(hovermode="x")
        fig.update_yaxes(autorange="reversed")
        fig.update_layout(yaxis2=dict(title='Misfit',overlaying='y',side='right',showgrid=False))
        misfit_trace = px.line(
            df_layers_long,
            x=self.settings.x_axis,
            y='misfit',
        ).data[0]

        misfit_trace.update(
            yaxis='y2',
            line=dict(color='black', width=2),
            name='Misfit',showlegend=True
        )
        fig.update_layout(yaxis2=dict(range=[0, 8]))

        fig.add_trace(misfit_trace)

        fig.update_layout(
        legend=dict(x=0.89, y=0.15,xanchor="left",yanchor="top",bgcolor="rgba(255,255,255,0.8)")
            )

        fig.update_layout(yaxis2=dict(title=dict(text="Misfit",standoff=10),overlaying="y",side="right",showgrid=False)
)
        x_vals = heatmap_df.columns.values
        x_min, x_max = np.nanmin(x_vals), np.nanmax(x_vals)

        y_min = df_layers_long["depth"].min()
        y_max = df_layers_long["depth"].max()
        ymax = df_layers_long["depth"].max()
        doi_df = (df_layers_long.groupby(self.settings.x_axis)["doi"].first().reset_index())
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([
                    [x_min],
                    doi_df[self.settings.x_axis].values,
                    [x_max],
                    [x_min]
                ]),
                y=np.concatenate([
                    [y_max],
                    doi_df["doi"].values,
                    [y_max],
                    [y_max]
                ]),
                fill="toself",
                fillcolor="rgba(255,255,255,0.6)",
                line=dict(width=0),
                hoverinfo="skip",
                name="Below DOI",
            )
        )

        fig.update_yaxes(
            range=[y_max, y_min-8],
            autorange=False,
            #title="Depth [m]"
        )

        fig.update_xaxes(
            range=[x_min, x_max],
            autorange=False
        )
        fig.update_layout(yaxis2=dict(range=[0, 8]))
        return fig


import dash_bootstrap_components as dbc

@dataclass
class StartingModelSettings(PanelSettings):
    line_color: str='#ff0000'

from anemone.inversion import LogResistivity

class StartingModel(ModelGraph):
    
    misfit = None
    def __init__(self, data, **kwargs):
        starting_model = kwargs.pop('starting_rho', 10.)
        settings = StartingModelSettings(id='starting_model', **kwargs)
        super().__init__(id='starting_model', settings=settings, starting_rho=starting_model)
        self.dataframe = data

    def misfit_render(self):
        fig = px.line(self.misfit)
        return fig


    def render(self):
        fig = px.line(self.dataframe,
            x='resistivity',
            y='depth',
            markers=True,
            color_discrete_sequence=[self.settings.line_color, self.settings.line_color],
            hover_data={'resistivity': ':.2f Ω⋅m', 'depth': False},
        )

        fig.update_layout(
            title='Inversion Starting Model',
            xaxis_title='resistivity [Ω⋅m]',
            yaxis_title='depth [m]',
            xaxis_type='log', 
            yaxis_type='linear',
            yaxis=dict(autorange='reversed'),
            xaxis=dict(range=[-0.1,3.1]),  
            showlegend=True,
            modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
        )
        fig.add_shape(type='line', x0=self.starting_rho, x1=self.starting_rho,
                      y0=self.dataframe['depth'].min(), y1=self.dataframe['depth'].max(),
                      xref='x1', yref='y1',
                      line=dict(color=self.settings.line_color, dash='dash'),
                      editable=True)

        return fig
    
    def initialize(self):
        init = html.Div([dbc.Container([
                dbc.Row([
                    dbc.Col(
                        dcc.Graph(figure=self.render(), id=self.id, mathjax=True, 
                                    config=dict(edits={'shapePosition':True}, displayModeBar=False)),
                            width=10),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                ], style={'height':'100%'})], style={'height':'95%', 'padding':'25px'}),
                 gear_maker(self.id)], style={'height': '100%', 'overflow': 'hidden'},
                  )
        return init
                            
    
    def add_callbacks(self, app):
        super().add_callbacks(app)

        @app.callback(
            Output(self.id, 'figure', allow_duplicate=True),
            Input(self.id, 'relayoutData'),
            prevent_initial_call=True
        )
        def update_starting_model(relayoutData):
            self.starting_rho = int(relayoutData.get('shapes[0].x0', self.starting_rho))
            self.dataframe['resistivity'] = self.starting_rho
            return self.render()
        

    @classmethod
    def standard(cls, rho=40.):
        df = pd.DataFrame({
            'resistivity': [rho] * 31,  # Default resistivity values
            'depth': np.cumsum(np.logspace(0, 1.3, 31)).tolist()  # Example depth values from 0 to 300 meters
            })
        return cls(data=df)
        
class Inversion_iterations(Panel):
    misfit = None
    starting_rho = 10.
    log_time_value = None
    dbdt = None
    def __init__(self, data,rho=10., **kwargs):
        self.rho = rho
        settings = StartingModelSettings(id='inv_it', **kwargs)
        super().__init__(id='inv_it', settings=settings)
        self.dataframe = data

    def render_init(self):
        COMMON_LAYOUT = dict(
            width=1000,
            height=850,
            margin=dict(l=60, r=40, t=90, b=45),
        )
        # self.dataframe = self.dataframe.reset_index(drop=True)
        if self.dataframe is None:
            df = pd.DataFrame({
                "resistivity": [self.rho] * 31,
                "depth": np.cumsum(np.logspace(0, 1.3, 31))
            })
        else:
            df = self.dataframe()
            # print(self.dataframe)
            # df['resistivity']= [self.rho]*31
            
        fig = make_subplots(
        rows=1,
        cols=2,
        column_widths=[0.45, 0.55],
        subplot_titles=(
            'Starting Model',
            'Sounding curve'
            )
        )
        depth = np.cumsum(np.logspace(0, 1.3, 31))
        rho = [self.rho]*31
        # -------- Left subplot: resistivity vs depth --------
        fig.add_trace(
            go.Scatter(
                x=rho,
                y=depth,
                mode='lines+markers',
                line=dict(color=self.settings.line_color),
                marker=dict(color=self.settings.line_color),
                hovertemplate='ρ: %{x:.2f} Ω⋅m<br>depth: %{y:.2f} m'
            ),
            row=1,
            col=1
        )

        # Vertical reference line
        fig.add_shape(
            type='line',
            x0=self.rho,
            x1=self.rho,
            y0=depth.min(),
            y1=depth.max(),
            line=dict(color=self.settings.line_color, dash='dash'),
            row=1,
            col=1
        )

        # for i, row in df.iterrows():
        #     fig.add_shape(
        #         type="line",
        #         x0=row["resistivity"] * 0.9,
        #         x1=row["resistivity"] * 1.1,
        #         y0=row["depth"],
        #         y1=row["depth"],
        #         editable=True,
        #         name=f"layer-{i}",
        #         # dragmode = 'select'
        #     )
        # fig.update_layout(dragmode="select")
        if isinstance(self.dbdt,list):
            # -------- Right subplot: db/dt vs time --------
            fig.add_trace(
                go.Scatter(
                    x=time,
                    y=dbdt,
                    mode='lines',
                    line=dict(color=self.settings.line_color),
                    hovertemplate='t: %{x:.3f} s<br>dB/dt: %{y:.3e}'
                ),
                row=1,
                col=2
            )
        else:
            fig.add_trace(
                go.Scatter(
                    x=[1e-6, 1e-2],
                    y=[1e-10, 1e-3],
                    mode="markers",
                    marker=dict(opacity=0),
                    showlegend=False
                ),
                row=1,
                col=2
            )

        # -------- Axes & layout formatting --------
        fig.update_xaxes(
            title_text='Resistivity [Ω⋅m]',
            type='log',
            range=[0, 2.7],
            showline=True,
            mirror=True,
            row=1,
            col=1
        )

        fig.update_yaxes(
            title_text='Depth [m]',
            range=[180, -0.5],
            showline=True,
            mirror=True,
            row=1,
            col=1
        )

        fig.update_xaxes(
            title_text='Time [s]',
            type = 'log',
            range=[-6,-2.1],
            showline=True,
            mirror=True,
            row=1,
            col=2
        )

        fig.update_yaxes(
            title_text='dB/dt [V / m²]',
            type = 'log',
            range = [-10, -3],
            showline=True,
            mirror=True,
            row=1,
            col=2
        )

        fig.update_layout(
            title = "SCI Inversion",
            showlegend=False,
            modebar=dict(
                remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']
            )
        )
        fig.update_layout(
                **COMMON_LAYOUT,
                #title='Select constraints and interact with map',
                showlegend=False
            )
        return fig
        # fig = px.line(df,
        #     x='resistivity',
        #     y='depth',
        #     markers=True,
        #     color_discrete_sequence=[self.settings.line_color, self.settings.line_color],
        #     hover_data={'resistivity': ':.2f Ω⋅m', 'depth': False},
        # )
        
        # fig.update_layout(
        #     title='Inversion Starting Model',
        #     xaxis_title='resistivity [Ω⋅m]',
        #     yaxis_title='depth [m]',
        #     xaxis_type='log',
        #     yaxis_type='linear',
        #     yaxis=dict(autorange='reversed'), 
        #     xaxis=dict(range=[-0.1,3.1]), 
        #     showlegend=True,
        #     modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
        # )
        # fig.add_shape(type='line', x0=self.rho, x1=self.rho,
        #               y0=df['depth'].min(), y1=df['depth'].max(),
        #               xref='x1', yref='y1',
        #               line=dict(color=self.settings.line_color, dash='dash'),
        #               editable=True)
        # fig.update_xaxes(showline=True, mirror=True)
        # fig.update_yaxes(showline=True, mirror=True)
        # return fig

    def render(self):
        if not isinstance(self.misfit, list):
            fig = self.render_init()

        elif len(self.misfit) == 0:
            fig = go.Figure()
            fig.update_layout(
                title='Inversion',
                xaxis_title='Iterations',
                yaxis_title='Misfit',
                xaxis_type='linear',
                yaxis_type='log',
                yaxis=dict(range=[-1,2]), 
                xaxis=dict(range=[-0.1,3+len(self.misfit)]),
                showlegend=True,
            )
            fig.update_xaxes(showline=True, mirror=True)
            fig.update_yaxes(showline=True, mirror=True)
        else:
            fig = px.line(
                x=self.iterations,
                y=self.misfit, labels={'x':'Iterations', 'y':'Misfit'},
                markers=True,
                color_discrete_sequence=[self.settings.line_color, self.settings.line_color],

            )

            fig.update_traces(name="Misfit", showlegend=True)
            
            
            fig = px.line(
                x=self.iterations,
                y=self.misfit, labels={'x':'Iterations', 'y':'Misfit'},
                markers=True,
                color_discrete_sequence=[self.settings.line_color, self.settings.line_color],

            )

            fig.update_traces(name="Total misfit", showlegend=True)

            fig.update_layout(
                title='Inversion',
                xaxis_title='Iterations',
                yaxis_title='Misfit',
                xaxis_type='linear',
                yaxis_type='log',
                yaxis=dict(range=[-1,2]),
                xaxis=dict(range=[-0.1,3+len(self.misfit)]),  
                showlegend=True,
            )
            fig.update_xaxes(showline=True, mirror=True)
            fig.update_yaxes(showline=True, mirror=True)
        return fig
    

    def initialize(self):
        init = html.Div([dbc.Container([
                dbc.Row([
                    dbc.Col(
                        dcc.Graph(figure=self.render_init(), id=self.id, mathjax=True, 
                                    config=dict(edits={'shapePosition':True}, displayModeBar=False)),
                            width=10),
                    dbc.Col([dbc.Button("invert all", id='invert_all_button', style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("invert selected", id='invert_selected_button', style={'width':'100%'}),
                             html.Div(style={'height':'30px'}), 
                             html.Div(
                            "Vertical constraints", style={"fontWeight": "bold", 'textAlign':'center'}),
                            html.Div(style={'height':'10px'}),
                            #  dbc.Button("Loose", id='vc_loose_button', color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                            #  html.Div(style={'height':'10px'}),
                            #  dbc.Button("Medium",id="vc_medium_button",color="primary",outline=True,disabled=True,style={"width": "100%"}),
                            #  html.Div(style={'height':'10px'}),
                            #  dbc.Button("Tight", id='vc_tight_button',color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                            #  html.Div(style={'height':'30px'}),
                            dbc.Button("Loose", id='vc_loose_button', color='secondary', outline=True, style={'width':'100%'}),
                            html.Div(style={'height':'10px'}),
                            dbc.Button("Medium",id='vc_medium_button',color='primary',outline=False,style={'width':'100%'}),
                            html.Div(style={'height':'10px'}),
                            dbc.Button("Tight", id='vc_tight_button',color='secondary', outline=True, style={'width':'100%'}),
                            html.Div(style={'height':'30px'}), 
                             html.Div(
                            "Horizontal constraints", style={"fontWeight": "bold", 'textAlign':'center'}),
                            html.Div(style={'height':'10px'}),
                             dbc.Button("Loose", id='hc_loose_button', color='secondary', outline=True, style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Medium",id="hc_medium_button",color="primary",outline=False,style={"width": "100%"}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Tight", id='hc_tight_button',color='secondary', outline=True, style={'width':'100%'}),
                             html.Div(style={'height':'30px'}),
                             dbc.Button("Starting model", id='reset_inv_model_button', color='secondary', style={'width':'100%'}),
                             html.Div(style={'height':'40px'}),
                             html.Div("Elapsed time: 0:00",id="inv-timer",style={"fontWeight": "bold","whiteSpace":"pre-line"}),] , width=2),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                ], style={'height':'100%'})], style={'height':'95%', 'padding':'25px'}),
                # html.Div(
                #             "Elapsed time: 0:00",
                #             id="inv-timer",
                #             style={"fontWeight": "bold"}
                #         ),
                 gear_maker(self.id)], style={'height': '100%', 'overflow': 'hidden'},
                  )
        return init                   
    
    def add_callbacks(self, app):
        super().add_callbacks(app)

        @app.callback(
            Output(self.id, 'figure', allow_duplicate=True),
            Output("inv-timer", "children"),
            Input('inv-log-poll', 'n_intervals'),
            prevent_initial_call=True
        )

        def update_misfit(n_intervals):
            log_time_value = None
            elapsed_seconds = n_intervals
            minutes, seconds = divmod(elapsed_seconds, 60)
            timer_text = f"Elapsed time: {int(minutes)}:{int(seconds):02d}"
            self.iterations = []
            self.misfit = []
            log_path = "inversion_log.txt"

            with open("inversion_log.txt", "r") as file:
                for line in file:
                    if not line.strip():
                        continue  # skip empty lines

                    parts = line.split()

                    # Iteration number is the first token
                    if not parts[0].isdigit():
                        continue  # skip lines that don't start with an iteration number
                    iteration = int(parts[0])

                    # Find "Total misfit:" and take the number after it
                    total_misfit_index = parts.index("Total") + 2
                    total_misfit = float(parts[total_misfit_index])

                    self.iterations.append(iteration)
                    self.misfit.append(total_misfit)

                    if "Last" in parts:
                        last_index = parts.index("Last")
                        target_index = last_index + 3
                        if target_index < len(parts):
                            log_time_value = parts[target_index]

            timer_text = f"Elapsed time: {int(minutes)}:{int(seconds):02d}"
            if log_time_value is not None:
                timer_text += f"\nLast iteration: {log_time_value} s"
            return self.render(), timer_text
        @app.callback(
            Output("starting_model", "figure"),
            Input("starting-model", "data"),
        )
        def sync_starting_model(data):
            df = pd.DataFrame({
                "resistivity": [data["rho"]] * len(data["depth"]),
                "depth": data["depth"]
            })
            stmod.dataframe = df
            return self.render()
        
        @app.callback(
            Output("inv_it", "figure", allow_duplicate=True),
            Input("reset_inv_model_button", "n_clicks"),
            prevent_initial_call=True
        )
        def reset_inv_model(n_clicks):
            return self.render_init()


        @app.callback(
            Output(self.id, "figure", allow_duplicate=True),
            Input(self.id, "relayoutData"),
            State("starting-model-selected", "data"),
            prevent_initial_call=True
        )
        def update_layers_from_drag(relayoutData, selected_indices):

            if not relayoutData or not selected_indices:
                raise PreventUpdate

            # Find which shape moved
            moved = [k for k in relayoutData if k.endswith(".x0")]
            if not moved:
                raise PreventUpdate

            key = moved[0]                 # e.g. "shapes[5].x0"
            shape_idx = int(key.split("[")[1].split("]")[0])

            new_x = relayoutData[key]

            # Reference old value
            old_x = df.loc[shape_idx, "resistivity"]
            delta = new_x - old_x

            # Apply delta only to selected layers
            for i in selected_indices:
                df.loc[i, "resistivity"] += delta

            return self.render_init()
        
        @app.callback(
            [
                Output('model_section', 'figure', allow_duplicate=True),
                Output('sounding', 'figure', allow_duplicate=True),
                Output('review_layout', 'n_clicks', allow_duplicate=True),
                Output('review_layout', 'disabled', allow_duplicate=True),
            ],
            Input('invert_all_button', 'n_clicks'),
            State('review_layout', 'n_clicks'),  # Add this state to get current value
            State("vc-level", "data"),
            State("hc-level", "data"),
            State("starting-model", "data"),
            running=[(Output("invert_all_button", "disabled"), True, False),
            (Output("invert_selected_button", "disabled"), True, False), 
            (Output("inv-log-poll", "disabled"), False, True),    
            (Output("vc_loose_button", "disabled"), True, False),
            (Output("vc_medium_button", "disabled"), True, False),
            (Output("vc_tight_button", "disabled"), True, False),
            (Output("hc_loose_button", "disabled"), True, False),
            (Output("hc_medium_button", "disabled"), True, False),
            (Output("hc_tight_button", "disabled"), True, False),
            (Output('reset_inv_model_button', "disabled"), True, False)],
            prevent_initial_call=True
        )
        def launch_inversion(n_clicks, current_review_clicks, vc_level,hc_level,starting_model):
            if n_clicks:
                df = self.dataframe()
                from torch import from_numpy, tensor
                print('starting model:', starting_model["rho"])
                rho = tensor(starting_model["rho"]).repeat(len(starting_model["depth"]))
                z   = tensor(starting_model["depth"][:-1])

                if vc_level == "loose":
                    Vert = 1.0
                elif vc_level == "medium":
                    Vert = 0.5
                elif vc_level == "tight":
                    Vert = 0.1

                if hc_level == "loose":
                    Horz = 1.0
                elif hc_level == "medium":
                    Horz = 0.6
                elif hc_level == "tight":
                    Horz = 0.3
                res_start                        = LogResistivity.smooth(rho,z) 
                # print(TABLES['data'])
                models, df = df.invert(res_start,vc = Vert, hc = Horz)
                mod1.dataframe                   = models.copy()
                mod2.dataframe                   = models.copy()
                dbdt1.dataframe                  = df['data'].copy()
                dbdt2.dataframe                  = df['data'].copy()
                new_review_clicks = (current_review_clicks or 0) + 1
                layouts.invert = layouts.invert_multi_first
                return mod2.render(), dbdt1.render(), new_review_clicks, False#, 0
            raise PreventUpdate


    @classmethod
    def standard(cls, misfit=None, rho=10.):
        return cls(data=misfit, rho=rho)

class Single_site(Panel):
    def __init__(self, data,rho=10., **kwargs):
        self.rho = rho
        settings = StartingModelSettings(id='inv-single', **kwargs)
        super().__init__(id='inv-single', settings=settings)
        self.dataframe = data

    def render(self, curves=None):
        COMMON_LAYOUT = dict(
            width=1000,
            height=850,
            margin=dict(l=60, r=40, t=90, b=45),
        )
        if curves is None:
            df = pd.DataFrame({
                'resistivity': [self.rho] * 31,
                'depth': np.cumsum(np.logspace(0, 1.3, 31))
            })

            fig = make_subplots(
                rows=1,
                cols=2,
                column_widths=[0.45, 0.55],
                subplot_titles=(
                    "Starting Model",
                    "Sounding curve"
                )
            )

            # ---- Resistivity model (left subplot) ----
            fig.add_trace(
                go.Scatter(
                    x=df['resistivity'],
                    y=df['depth'],
                    mode='lines+markers',
                    line=dict(color=self.settings.line_color),
                    marker=dict(color=self.settings.line_color),
                    hovertemplate="Resistivity: %{x:.2f} Ω⋅m<br>Depth: %{y:.2f} m<extra></extra>",
                    name="Starting model"
                ),
                row=1,
                col=1
            )
            fig.add_shape(type='line', x0=self.rho, x1=self.rho,
                y0=df['depth'].min(), y1=df['depth'].max(),
                xref='x1', yref='y1',
                line=dict(color=self.settings.line_color, dash='dash'),
                editable=True)

            fig.update_xaxes(
                title_text='Resistivity [Ω⋅m]',
                type='log',
                range=[0, 2.7],
                row=1,
                col=1,
                showline=True,
                mirror=True
            )

            fig.update_yaxes(
                title_text='Depth [m]',
                range=[180, -0.5],  # depth increasing downward
                row=1,
                col=1,
                showline=True,
                mirror=True,
            )

            fig.update_xaxes(
                title_text='Time [s]',
                range=[-6,-2.1],
                type='log',
                row=1,
                col=2,
                showline=True,
                mirror=True,
            )
            fig.update_yaxes(
                title_text='dB/dt [V / m²]',
                range=[-10,-3],
                type='log',
                row=1,
                col=2,
                showline=True,
                mirror=True,
            )

            fig.add_trace(
                go.Scatter(
                    x=[1e-6, 1e-2],
                    y=[1e-10, 1e-3],
                    mode="markers",
                    marker=dict(opacity=0),
                    showlegend=False
                ),
                row=1,
                col=2
            )
            fig.update_layout(
                **COMMON_LAYOUT,
                title='Select constraints and interact with map',
                showlegend=False
            )
            return fig

        
        VC_COLORS = {
        "loose":  "#2D81FF",
        "medium": "#00A676",
        "tight":  "#E63946",
        }

        fig = make_subplots(
            rows=1,
            cols=2,
            column_widths=[0.45, 0.55],
            subplot_titles=(
                "Resistivity Model",
                "Sounding curve"
            )
        )

        include = curves[0][9]   # include mask (same for all curves)
        time    = curves[0][7]
        dbdt_obs = curves[0][5]
        error    = curves[0][8]

        opacity = np.where(include, 1.0, 0.2)

        y_inc = dbdt_obs[include]
        e_inc = error[include] / 100

        err_plus  = y_inc * e_inc
        err_minus = y_inc * e_inc / (1 + e_inc)

        inc = include

        y = dbdt_obs[inc]
        e = error[inc] / 100

        err_plus  = y * e
        err_minus = y * e / (1 + e)

        fig.add_trace(
            go.Scatter(
                x=time[inc],
                y=y,
                mode="markers",
                name="Observed dB/dt",
                marker=dict(
                    color="black",
                    size=6,
                ),
                error_y=dict(
                    type="data",
                    array=err_plus,
                    arrayminus=err_minus,
                    visible=True,
                    thickness=1,
                    width=0,
                ),
            ),
            row=1,
            col=2,
        )
        
        exc = ~include

        fig.add_trace(
            go.Scatter(
                x=time[exc],
                y=dbdt_obs[exc],
                mode="markers",
                showlegend=False,
                marker=dict(
                    color="black",
                    size=6,
                    opacity=0.2,
                ),
            ),
            row=1,
            col=2,
        )

        for (
            vc,
            rho,
            depth,
            misfit,
            df_layers,
            dbdt_obs,
            dbdt_syn,
            time,
            error,
            include, doi
        ) in curves:
            rho = np.insert(np.array(rho),0,rho[0])
            depth = np.insert(np.array(depth),0,0)
            color = VC_COLORS.get(vc, "black")

            fig.add_trace(
                go.Scatter(
                    x=rho,
                    y=depth,
                    mode="lines",
                    line=dict(color=color, width=3),
                    line_shape="hv",
                    name=f"{vc.capitalize()} (misfit = {misfit:.2f})",
                    legendgroup=vc,
                ),
                row=1,
                col=1
            )

            fig.add_trace(
                go.Scatter(
                    x=time,
                    y=dbdt_syn,
                    mode="lines",
                    line=dict(color=color),
                    name=f"{vc} syn",
                    legendgroup=vc,
                    showlegend=False,
                ),
                row=1,
                col=2
            )
        
        fig.add_trace(
            go.Scatter(
            x=[0.1,1000],
            y=[doi[0],doi[0]],
            mode="lines",
            line=dict(color="black",
                width=2,
                dash="dash"),
                showlegend=False,
            ),
            row=1,
            col=1
        )
        
        fig.update_yaxes(
            range=[180, -0.5],  # depth increasing downward
            title_text="Depth [m]",
            row=1,
            col=1,
            showline=True,
            mirror=True,
            linewidth=1,
            linecolor='black'
        )

        fig.update_xaxes(
            type="log",
            range=[0,2.7],
            title_text="Resistivity [Ωm]",
            row=1,
            col=1,
            showline=True,
            mirror=True,
            linewidth=1,
            linecolor='black'
        )

        fig.update_xaxes(
            type="log",
            title_text="Time [s]",
            row=1,
            col=2,
            showline=True,
            mirror=True,
            linewidth=1,
            linecolor='black'
        )

        fig.update_yaxes(
            type="log",
            title_text="dB/dt [V / m²]",
            row=1,
            col=2,
            showline=True,
            mirror=True,
            linewidth=1,
            linecolor='black'
        )

        # ---- LAYOUT ----
        fig.update_layout(
            **COMMON_LAYOUT,
            legend=dict(
                #title="Vertical constraint",
                orientation="h",
                yanchor="bottom",
                y=1.05,
                xanchor="center",
                x=0.5,
            ),
            modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
        )

        return fig
    

    def initialize(self):
        init = html.Div([dbc.Container([
                dbc.Row([
                    dbc.Col(
                        dcc.Graph(figure=self.render(), id=self.id, mathjax=True, 
                                    config=dict(edits={'shapePosition':True}, displayModeBar=False)),
                            width=10),
                    dbc.Col([html.Div(
                            "Vertical constraints", style={"fontWeight": "bold", 'textAlign':'center'}),
                            html.Div(style={'height':'10px'}),
                             dbc.Button("Loose", id='vc_sing_loose_button', color='secondary', outline=True, style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Medium",id="vc_sing_medium_button",color="primary",outline=False,style={"width": "100%"}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Tight", id='vc_sing_tight_button',color='secondary', outline=True, style={'width':'100%'}),
                             html.Div(style={'height':'30px'}), 
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Starting model",id="reset_single_model_button",color="secondary",style={"width": "100%"})], width=2),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                ], style={'height':'100%'})], style={'height':'95%', 'padding':'25px'}),
                 gear_maker(self.id)], style={'height': '100%', 'overflow': 'hidden'},
                  )
        return init
    
    def add_callbacks(self, app):
        super().add_callbacks(app)
        
        @app.callback(
            Output("starting_model_Sing", "figure"),
            Input("starting-model", "data"),
        )
        def sync_starting_model(data):
            df = pd.DataFrame({
                "resistivity": [data["rho"]] * len(data["depth"]),
                "depth": data["depth"]
            })
            stmod.dataframe = df
            return self.render()

        @app.callback(
            Output("inv-single", "figure", allow_duplicate=True),
            Input("reset_single_model_button", "n_clicks"),
            prevent_initial_call=True
        )
        def reset_inv_model(n_clicks):
            curves = None
            return self.render()


    @classmethod
    def standard(cls, misfit=None, rho=10.):
        return cls(data=misfit, rho=rho)#cls(data=df)