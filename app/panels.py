from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table
import numpy as np

import plotly.io as pio

from typing import Literal
import plotly.express as px
import plotly.graph_objects as go

import os
import base64
import rasterio
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import reshape_as_image
from PIL import Image
from pyproj import Transformer
import pandas as pd
import math

import matplotlib.cm as cm
import matplotlib.colors as mcolors

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod

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
    plot_attribute:  Literal['date', 'daytime', 'Data Residual','DOI', 'Number of Gates'] = 'date'


class Map(Panel):
    dataframe: None
    highlighted: int = None

    def __init__(self, data, **kwargs):
        settings = MapSettings(id='map', **kwargs)
        super().__init__(id='map', settings=settings)
        self.dataframe = data

    def render(self):
        if self.dataframe is None: return self.empty_render()

        fig = px.scatter_map(self.dataframe, lat="latitude", lon="longitude", zoom=self.settings.zoom)#, color_discrete_sequence=[self.settings.color])  color=self.settings.plot_attribute,
        fig.update_layout(map_style="white-bg", coloraxis_showscale=False, 
            map_layers=[
                {
                    "below": 'traces',
                    "sourcetype": "raster",
                    "sourceattribution": "Google Earth (C)",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }]) #,coloraxis_showscale=False
        fig.update_traces(marker=dict(color=self.settings.color,showscale=False) )
        
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
            title="dbdt vs time by site_id",
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
            title="dbdt vs time by site_id",
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
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb
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
            session_text+= f"- no recent sessions\n"
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
        # with self.dataframe._skip_tracking():
        df_layers_long = self.dataframe.melt(
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
        fig.update_layout(hovermode="x")
        fig.update_yaxes(autorange="reversed")
        return fig




# panel_list = html.Div([
#     html.H1("Panels"),
#     html.H2("Data"),
#     html.Ul([
#         html.Li([
#             dcc.Link("Sounding", href="#sounding"),
#             " ",
#             dcc.Link("[+]", href="#new_sounding")
#         ]),
#         html.Li([
#             dcc.Link("Section", href="#section"),
#             " ",
#             dcc.Link("[+]", href="#new_section")
#         ]),
#     ]),
#     html.H2("Models"),
#     html.Ul([
#         html.Li([
#             dcc.Link("Graph", href="#graph"),
#             " ",
#             dcc.Link("[+]", href="#new_graph")
#         ]),
#         html.Li([
#             dcc.Link("Colorbar", href="#colorbar"),
#             " ",
#             dcc.Link("[+]", href="#new_colorbar")
#         ]),
#         html.Li([
#             dcc.Link("Table", href="#table"),
#             " ",
#             dcc.Link("[+]", href="#new_table")
#         ]),
#     ]),
# ])

import dash_bootstrap_components as dbc

@dataclass
class StartingModelSettings(PanelSettings):
    line_color: str='#ff0000'

from anemone.inversion import LogResistivity

class StartingModel(ModelGraph):
    starting_rho: float = 10.
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
        #if len(self.misfit) > 0: return self.empty_render()

        # fig = make_subplots(rows=1, cols=2, shared_yaxes=True)
        # Add the step plot for resistivity
        fig = px.line(self.dataframe,
            x='resistivity',
            y='depth',
            markers=True,
            color_discrete_sequence=[self.settings.line_color, self.settings.line_color],
            hover_data={'resistivity': ':.2f Ω⋅m', 'depth': False},  # Add tooltip for resistivity values
            # hover='resistivity'  # Add tooltip for resistivity values
        )
        
        for i in [0.5, 1, 2]:
            z = self.dataframe['depth']
            y = 10+90*(1 / (1 + np.exp(-20.*(z-150)/z.max())))**i
            fig.add_scatter(x=y, y=z, line=dict(color='grey'))#, row=1, col=2)

        # Update layout to match typical resistivity plot conventions
        fig.update_layout(
            title='Inversion Starting Model',
            xaxis_title='resistivity [Ω⋅m]',
            yaxis_title='depth [m]',
            xaxis_type='log',  # Resistivity is typically plotted on log scale
            yaxis_type='linear',
            yaxis=dict(autorange='reversed'),  # Depth increases downward
            xaxis=dict(range=[-0.1,3.1]),  # Set x-axis range for resistivity
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
                    dbc.Col([dbc.Button("invert all", id='invert_all_button', style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("invert selected", id='invert_selected_button', style={'width':'100%'})] , width=2),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                    # dbc.Col(html.Button("invert selected", id='invert_selected_button'), width=1)
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
            'depth': np.logspace(0, np.log10(300), 31)  # Example depth values from 0 to 300 meters
            })
        return cls(data=df)
    


# --------------------- Settings ---------------------
class ScatterMapSettings(PanelSettings):
    color = "red"
    highlight_color = "yellow"
    zoom = 10
    png_crs = "EPSG:32637"

# ------------------- Helper: Layers/Opacity Box -------------------
def layer_row(label, layer_id, checked=False, default_opacity=1.0):
        return html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "6px",
                "position": "relative",
                "marginBottom": "6px",
            },
            children=[
                dcc.Checklist(
                    id={"type": "layer-check", "layer": layer_id},
                    options=[{"label": "", "value": "on"}],
                    value=["on"] if checked else [],
                    style={"margin": 0},
                ),
                html.Span(label, style={"flex": "1"}),

                html.Button(
                    "⋮",
                    id={"type": "layer-menu-btn", "layer": layer_id},
                    style={
                        "border": "none",
                        "background": "none",
                        "cursor": "pointer",
                        "fontSize": "16px",
                    },
                ),

                html.Div(
                    id={"type": "layer-menu", "layer": layer_id},
                    style={
                        "display": "none",
                        "position": "absolute",
                        "right": "0",
                        "top": "24px",
                        "background": "white",
                        "padding": "8px",
                        "borderRadius": "4px",
                        "boxShadow": "0 2px 6px rgba(0,0,0,0.25)",
                        "zIndex": 4000,
                        "width": "160px",
                    },
                    children=[
                        html.Label("Opacity"),
                        dcc.Slider(
                            id={"type": "layer-opacity", "layer": layer_id},
                            min=0, max=1, step=0.05,
                            value=default_opacity,
                            marks={0: "0", 0.5: "0.5", 1: "1"},
                        ),
                    ],
                ),
            ],
        )




    # ------------------------- double click line lat lon save as strings -------------------------
    

# --------------------- ScatterMapRenderer ---------------------
class ScatterMapRenderer(Panel):
    def __init__(self, 
                 dataframe, 
                 highlighted=None,
                 tiff_path=None,
                 png_path=None,
                 **kwargs
                 ):
        settings = kwargs.pop('settings', ScatterMapSettings('scatter_map'))
        super().__init__(id='scatter_map', settings=settings)
    
        self.dataframe = dataframe
        self.settings = settings
        self.highlighted = highlighted
        self.tiff_path = tiff_path
        self.png_path = png_path

        self.tiff_info = self._load_tiff() if tiff_path else None
        self.png_info = self._load_png() if png_path else None

        if self.tiff_info and self.png_info:
            self._check_bounds_match()  

    # ------------------- Helper: load PNG -------------------
    def _load_png(self):
        pgw = os.path.splitext(self.png_path)[0] + ".pgw"
        if not os.path.exists(pgw):
            raise ValueError("PNG requires PGW or manual bounds")

        if self.png_path.lower().endswith(".png"):
            bounds = self._read_world_file(self.png_path)

            # Fallback to manual bounds
            if bounds is None:
                if not hasattr(self.settings, "png_bounds"):
                    raise ValueError(
                        "PNG file has no world file. Please provide bounds in settings.png_bounds = (left, bottom, right, top)"
                    )
                bounds = self.settings.png_bounds

        if hasattr(self.settings, "png_crs"):
            bounds = self._reproject_bounds(bounds, self.settings.png_crs)

        return {
            "image": self._image_to_data_uri(self.png_path),
            "bounds": bounds,}

    # ------------------- Helper: load TIFF -------------------
    def _load_tiff(self):
        reproj = self.tiff_path.replace(".tiff", "_wgs84.tiff")
        tiff_path = self._reproject_to_wgs84(self.tiff_path, reproj)

        with rasterio.open(tiff_path) as ds:
            bounds = ds.bounds
            png = reproj.replace(".tiff", ".png")

            if not os.path.exists(png):
                  # Read bands
                if ds.count >= 3:
                    img = ds.read([1,2,3])
                    img = reshape_as_image(img)
                else:
                    img = ds.read(1)

                lat_range = bounds.top - bounds.bottom
                lon_range = bounds.right - bounds.left
                aspect_ratio = lon_range / lat_range

                plt.figure(figsize=(100 * aspect_ratio, 100), dpi=100)

                plt.figure(figsize=(100 * aspect_ratio, 100), facecolor="white")
                plt.imshow(img, origin="upper")
                plt.axis("off")
                plt.savefig(png, bbox_inches="tight", pad_inches=0, facecolor="white")
                plt.close()

        return {
            "image": self._image_to_data_uri(png),
            "bounds": (bounds.left, bounds.bottom, bounds.right, bounds.top),}
  
    # ------------------------- GEOREFERENCE & CONVERSION -------------------------
    def _reproject_to_wgs84(self, src_path, dst_path):
        """Reproject any CRS TIFF to EPSG:4326"""
        with rasterio.open(src_path) as src:
            if src.crs.to_epsg() == 4326:
                return src_path  # already WGS84

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds)

            kwargs = src.meta.copy()
            kwargs.update({"crs": "EPSG:4326", "transform": transform,
                           "width": width, "height": height})

            with rasterio.open(dst_path, "w", **kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs="EPSG:4326",
                        resampling=Resampling.bilinear,)
        return dst_path

    def _reproject_bounds(self, bounds, src_crs):
        """Reproject bounds from src_crs to EPSG:4326"""
        left, bottom, right, top = bounds
        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        lon_left, lat_bottom = transformer.transform(left, bottom)
        lon_right, lat_top = transformer.transform(right, top)
        # Ensure top > bottom
        if lat_top < lat_bottom:
            lat_top, lat_bottom = lat_bottom, lat_top
        return (lon_left, lat_bottom, lon_right, lat_top)

    def _image_to_data_uri(self, path):       
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    # ------------------------- WORLD FILE HANDLING -------------------------
    def _read_world_file(self, png_path):
        """Read .pgw world file and return bounds in projected units"""
        world_file = os.path.splitext(png_path)[0] + ".pgw"
        if not os.path.exists(world_file):
            return None
        with open(world_file) as f:
            a = float(f.readline().strip())  # pixel width
            d = float(f.readline().strip())  # rotation x
            b = float(f.readline().strip())  # rotation y
            e = float(f.readline().strip())  # pixel height (usually negative)
            c = float(f.readline().strip())  # top-left X
            f_ = float(f.readline().strip()) # top-left Y

        img = Image.open(png_path)
        width, height = img.size

        left = c
        right = c + a * width
        if e < 0:
            top = f_
            bottom = f_ + e * height
        else:
            bottom = f_
            top = f_ + e * height

        # Ensure top > bottom
        if top < bottom:
            top, bottom = bottom, top

        return left, bottom, right, top

    # ------------------- Check bounds of png and Tiff -------------------
    def _check_bounds_match(self):
        if not self.tiff_info or not self.png_info:
            print("⚠️ One of the layers is missing – cannot compare bounds")
            return

        lt, bt, rt, tt = self.tiff_info["bounds"]
        lp, bp, rp, tp = self.png_info["bounds"]

        print("\n--- BOUNDS CHECK (WGS84) ---")
        print(f"TIFF bounds: lon [{lt:.6f}, {rt:.6f}], lat [{bt:.6f}, {tt:.6f}]")
        print(f" PNG bounds: lon [{lp:.6f}, {rp:.6f}], lat [{bp:.6f}, {tp:.6f}]")

        lon_overlap = not (rp < lt or lp > rt)
        lat_overlap = not (tp < bt or bp > tt)

        print(f"Longitude overlap: {lon_overlap}")
        print(f" Latitude overlap: {lat_overlap}")

        if lon_overlap and lat_overlap:
            print("✅ Bounds OVERLAP correctly")
        else:
            print("❌ Bounds DO NOT overlap")

    # ------------------- Map layers -------------------
    def _build_map_layers(self, show_google, show_tiff, show_png, google_op, tiff_op, png_op):
        layers = []

            # --- Bottom layer: Google Earth ---
        if show_google:
            layers.append({
            "sourcetype": "raster",
            "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"],
            "sourceattribution": "Google Earth (C)",
            "below": "traces",  # keep it below the points
            "opacity": google_op,
            })

        # --- TIFF layer ---
        if show_tiff and self.tiff_info:
            l, b, r, t = self.tiff_info["bounds"]
            layers.append({
                "below": "traces",
                "sourcetype": "image",
                "source": self.tiff_info["image"],
                "coordinates": [[l, t], [r, t], [r, b], [l, b]],
                "opacity": tiff_op,
            })

        # --- PNG layer ---
        if show_png and self.png_info:
            l, b, r, t = self.png_info["bounds"]
            layers.append({
                "below": "traces",
                "sourcetype": "image",
                "source": self.png_info["image"],
                "coordinates": [[l, t], [r, t], [r, b], [l, b]],
                "opacity": png_op,
            })
        print("MAP LAYERS:", len(layers))
        return layers
    
    # ------------------- Estimate points' center -------------------
    def _compute_df_center(self):
        """Return dict(lat=..., lon=...) as the center of the dataframe points"""
        if self.dataframe is None or self.dataframe.empty:
            # fallback center (0,0)
            return dict(lat=0, lon=0)
        return dict(
            lat=self.dataframe["latitude"].mean(),
            lon=self.dataframe["longitude"].mean()
        )
  


    # ------------------------- Render figure -------------------------
    def render(self, show_google=True ,show_tiff=True, show_png=True, show_points=True, 
               google_op=1, tiff_op=0.6, png_op=0.6, line_color='yellow', view=None, 
               preview_line=None, final_line=None, selected_idx=None):
        
        if self.dataframe is None or self.dataframe.empty:
            return None
            # --- Decide zoom & center ---
        zoom = view.get("zoom") if view and "zoom" in view else self.settings.zoom
        center = view.get("center") if view and "center" in view else self._compute_df_center()
        
        # figure without the points
        fig = px.scatter_map(
            self.dataframe.iloc[0:0],  # empty base
            lat="latitude",
            lon="longitude",
            zoom=zoom,
            center=center,)
        
        # --- Build figure ---
        if show_points:
            fig = px.scatter_map(self.dataframe,lat="latitude",lon="longitude",zoom=zoom,center=center,)

            fig.update_traces(marker=dict(size=18, color=self.settings.color), showlegend=False)

        fig.update_layout(
            map_style="white-bg",
            map_layers=self._build_map_layers(show_google, show_tiff, show_png, google_op, tiff_op, png_op),
            coloraxis_showscale=False,
            uirevision="keep",
            margin=dict(r=0, t=0, l=0, b=0),
            
            modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
            # shapes=[],
            newshape=dict( line_color='cyan', line_width=3, ),
            dragmode='pan'
        )

        # --- Highlight ---
        if self.highlighted is not None and show_points:
            df_h = self.dataframe.loc[[self.highlighted]]
            hfig = px.scatter_map(df_h, lat="latitude", lon="longitude")
            hfig.update_traces(marker=dict(size=20, color=self.settings.highlight_color), showlegend=False)
            for tr in hfig.data:
                fig.add_trace(tr)
    
    
        # =====================================================
        #           DRAW ALL FINAL SAVED LINES
        # =====================================================

        final_lines = final_line or []
        preview_line = preview_line or []

        for i,line in enumerate(final_lines):
            if not isinstance(line, (list, tuple)) or len(line) != 2:
                continue
            p0, p1 = line

            # Highlight selected line in Red, others in Yellow
            color = "red" if i == selected_idx else line_color
            width = 10 if i == selected_idx else 6

            fig.add_trace(
                go.Scattermap(
                    lon=[p0[0], p1[0]],
                    lat=[p0[1], p1[1]],
                    mode="lines",
                    line=dict(color=color, width=width),
                    name=f"Line {i+1}",
                    showlegend=False,
                    # hoverinfo="none"
                )
            )

        return fig
    

    def initialize(self):
        return html.Div(
            style={"height": "100vh", "position": "relative", "fontFamily": "sans-serif"},
            children=[
                # ---- STORES ----
                dcc.Store(id="layers-store"),
                dcc.Store(id="opacity-store"),
                dcc.Store(id="line-preview-store"),
                dcc.Store(id="line-final-store"),
                dcc.Store(id="section-mode-store", data="blocky"),
                dcc.Store(id="map-view-store"),
                dcc.Store(id="selected-line-index", data=0), # Tracks the 👁️ selection

                # ---- TOP CONTROL BAR ----
                html.Div(
                    style={
                        "display": "flex", 
                        "gap": "10px", 
                        "position": "absolute", 
                        "top": "10px", 
                        "left": "10px", 
                        "zIndex": 4000,
                        "alignItems": "flex-start"
                    },
                    children=[
                        # --- Layers Button ---
                        html.Div(
                            style={"position": "relative"},
                            children=[
                                html.Button("Layers ▼", id="layers-toggle", style={"padding": "5px 10px"}),
                                html.Div(
                                    id="layers-panel",
                                    style={
                                        "display": "none",
                                        "position": "absolute",
                                        "background": "white",
                                        "padding": "10px",
                                        "marginTop": "6px",
                                        "borderRadius": "6px",
                                        "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
                                        "width": "220px",
                                    },
                                    children=[
                                        layer_row("Google", "google", checked=True, default_opacity=1),
                                        layer_row("TIFF", "tiff", default_opacity=0.6),
                                        layer_row("PNG", "png", default_opacity=0.6),
                                        layer_row("Points", "points", checked=True, default_opacity=1),
                                    ],
                                ),
                            ]
                        ),

                        # --- Section Mode Button ---
                        html.Div(
                            style={"position": "relative"},
                            children=[
                                html.Button("Section ▼", id="section-toggle", style={"padding": "5px 10px"}),
                                html.Div(
                                    id="section-panel",
                                    style={
                                        "display": "none",
                                        "position": "absolute",
                                        "background": "white",
                                        "padding": "8px",
                                        "borderRadius": "6px",
                                        "boxShadow": "0 2px 6px rgba(0,0,0,0.25)",
                                        "marginTop": "4px",
                                        "minWidth": "140px",
                                    },
                                    children=[
                                        html.Div("Interpolated", id={"type": "section-option", "mode": "interp"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                        html.Div("Blocky", id={"type": "section-option", "mode": "blocky"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                        html.Div("Combined", id={"type": "section-option", "mode": "combined"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                    ],
                                ),
                            ]
                        ),

                        # --- Profiles/Lines Dropdown Panel ---
                        html.Div(
                            style={"position": "relative"},
                            children=[
                                html.Button("Lines ▼", id="profiles-toggle", style={"padding": "5px 10px"}),
                                html.Div(
                                    id="profiles-panel",
                                    style={
                                        "display": "none", 
                                        "position": "absolute",
                                        "background": "white",
                                        "padding": "12px",
                                        "marginTop": "6px",
                                        "borderRadius": "6px",
                                        "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
                                        "width": "280px", # Increased slightly for icon spacing
                                    },
                                    children=[
                                        html.Div("Active Profiles", style={"fontWeight": "bold", "marginBottom": "8px", "fontSize": "13px"}),
                                        
                                        # This container is populated dynamically by the master_line_controller callback
                                        html.Div(
                                            id="profile-list-container",
                                            style={
                                                "maxHeight": "250px", 
                                                "overflowY": "auto", 
                                                "marginBottom": "10px",
                                                "border": "1px solid #eee",
                                                "borderRadius": "4px"
                                            }
                                        ),
                                        
                                        html.Hr(style={"margin": "10px 0", "border": "0", "borderTop": "1px solid #eee"}),
                                        
                                        # Action Buttons
                                        html.Div(
                                            style={"display": "flex", "gap": "8px"},
                                            children=[
                                                html.Button(
                                                    "Clear Selected", 
                                                    id="clear-selected-btn", 
                                                    style={"fontSize": "11px", "flex": 1, "padding": "5px", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}
                                                ),
                                                html.Button(
                                                    "Clear All", 
                                                    id="clear-all-btn", 
                                                    style={"fontSize": "11px", "flex": 1, "padding": "5px", "color": "red", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}
                                                ),
                                            ]
                                        )
                                    ]
                                ),
                            ]
                        ),
                    ],
                ),

                # ---- MAP ----
                dcc.Graph(figure=self.render(), id=self.id, mathjax=True, 
                                   style={'height':'98%', 'width': '98%', 'align': 'center'}),

                # # ---- PROFILE PLOT ----
                # dcc.Graph(
                #     id="profile-plot",
                #     style={
                #         "height": "250px",
                #         "position": "absolute",
                #         "bottom": "10px",
                #         "left": "10px",
                #         "right": "10px",
                #         "zIndex": 2000,
                #         "background": "white",
                #         "borderRadius": "8px",
                #         "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)"
                #     },
                # ),

                gear_maker(self.id),
            ],
        )
    
    def add_callbacks(self, app):
        self.settings.add_callbacks(app)
        # super().add_callbacks(app)

        def toggle_layers_panel(n, style):
            if not n:
                return style
            return {**style,"display": "block" if style["display"] == "none" else "none",}

        toggle_layers_panel = app.callback(
            Output("layers-panel", "style"),    
            Input("layers-toggle", "n_clicks"),
            State("layers-panel", "style"),
        )(toggle_layers_panel)

        # --------------------- Toggle 3-dot menu per layer ---------------------
        def toggle_layer_menu(n, style):
            if not n:
                return style
            return {**style,"display": "block" if style["display"] == "none" else "none",}

        toggle_layer_menu = app.callback(
            Output({"type": "layer-menu", "layer": MATCH}, "style"),
            Input({"type": "layer-menu-btn", "layer": MATCH}, "n_clicks"),
            State({"type": "layer-menu", "layer": MATCH}, "style"),
            )(toggle_layer_menu)

