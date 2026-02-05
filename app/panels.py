from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table
import numpy as np
from nosj import nosj

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
from Sections_plotting import *

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
pio.templates["custom"] = custom_template
pio.templates.default = "custom"

@nosj
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
        



@nosj
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


@nosj
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

@nosj
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
        if self.session_files is None or len(self.session_files) == 0:
            session_text += "no previous session:\n"
        else:
            for f in self.session_files:
                cfolder = f.strip().replace('\\', '/')
                session_text += f"- [{cfolder}](#load=\"{cfolder.replace(' ', '%20')}\")\n"
        session_text += "- [open session](#open_session)\n"
        return html.Div([
            dcc.Markdown("# Welcome to sea anemone", style={'textAlign': 'center'}),       
            dcc.Markdown("### Upload your data to get started."),
            self.render(),
            html.Div([
                html.Div(['working directory: '], id="current-working-directory-label", style={"marginLeft":"10px", "marginTop": "10px", 'display': 'inline-block'}),
                html.A("select directory", href="#change_working", id="current-working-directory", style={"cursor": "pointer", "color": "blue", "textDecoration": "underline", "marginLeft":"10px", "marginTop": "10px", 'display': 'inline-block'}, title='change directory')
            ]),
            dcc.Markdown("---"),
            dcc.Markdown(session_text),
            gear_maker(self.id)],
            style={'margin':'10px'}#,'height': 'calc(100%-30px)', 'overflow': 'hidden'} 
        )


@nosj
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
@nosj
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
    
@nosj
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
        fig.update_layout(yaxis2=dict(title='Misfit',overlaying='y',side='right',showgrid=False))

        # misfit_trace = px.line(
        #     df_layers_long,
        #     x=self.settings.x_axis,
        #     y='misfit',
        # ).data[0]

        # misfit_trace.update(
        #     yaxis='y2',
        #     line=dict(color='black', width=2),
        #     name='Misfit',showlegend=True
        # )
        # fig.update_layout(yaxis2=dict(range=[0, 8]))

        # fig.add_trace(misfit_trace)

        fig.update_layout(
        legend=dict(x=0.95, y=0.11,xanchor="left",yanchor="top",bgcolor="rgba(255,255,255,0.8)")
            )

        fig.update_layout(yaxis2=dict(title=dict(text="Misfit",standoff=10),overlaying="y",side="right",showgrid=False)
)

        return fig


import dash_bootstrap_components as dbc


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
        
        # for i in [0.5, 1, 2]:
        #     z = self.dataframe['depth']
        #     y = 10+90*(1 / (1 + np.exp(-20.*(z-150)/z.max())))**i
        #     fig.add_scatter(x=y, y=z, line=dict(color='grey'))#, row=1, col=2)

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
                    #dbc.Col([dbc.Button("invert all", id='invert_all_button', style={'width':'100%'}),
                   #          html.Div(style={'height':'10px'}),
                   #          dbc.Button("invert selected", id='invert_selected_button', style={'width':'100%'})] , width=2),
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
    

class PyInterpretter(Panel):
    def __init__(self):
        super().__init__(id='pyinterp')

    def initialize(self):
        init = html.Div([
            html.H2("Python Interpreter"),
            dcc.Textarea(
                id='code-input',
                placeholder='Type Python code here...',
                style={'width': '100%', 'height': 200}
            ),
            html.Br(),
            html.Button('Run Code', id='run-btn', n_clicks=0),
            html.H4("Output:"),
            html.Pre(id='code-output', style={'backgroundColor': '#f4f4f4', 'padding': '10px'})
        ])
        return init
    # def add_callbacks(self, app):
    #     import sys
    #     import io
    #     import traceback
    #     import numpy as np        
    #     @app.callback(
    #         Output('code-output', 'children'),
    #         Input('run-btn', 'n_clicks'),
    #         State('code-input', 'value')
    #     )
    #     def run_python_code(n_clicks, code):
    #         if not code:
    #             return "No code entered."

    #         # Redirect stdout and stderr
    #         old_stdout = sys.stdout
    #         old_stderr = sys.stderr
    #         redirected_output = sys.stdout = io.StringIO()
    #         redirected_error = sys.stderr = io.StringIO()

    #         try:
    #             # Execute the code in a restricted namespace
    #             exec(code)#, {"__builtins__": __builtins__}, {})
    #             output = redirected_output.getvalue()
    #             errors = redirected_error.getvalue()
    #             return output + errors if output or errors else "Code executed successfully (no output)."
    #         except Exception:
    #             return traceback.format_exc()
    #         finally:
    #             # Restore stdout and stderr
    #             sys.stdout = old_stdout
    #             sys.stderr = old_stderr
        
class Inversion_iterations(Panel):
    #iterations = [1]
    misfit = None
    starting_rho = 10.
    log_time_value = None
    def __init__(self, data,rho=10., **kwargs):
        self.rho = rho
        settings = StartingModelSettings(id='inv_it', **kwargs)
        super().__init__(id='inv_it', settings=settings)
        self.dataframe = data

    # def misfit_render(self):
    #     fig = px.line(self.misfit)
    #     return fig

    def render_init(self):
        
        df = pd.DataFrame({
            'resistivity': [self.rho] * 31,  # Default resistivity values
            'depth': np.logspace(0, np.log10(300), 31)  # Example depth values from 0 to 300 meters
            })
        fig = px.line(df,
            x='resistivity',
            y='depth',
            markers=True,
            color_discrete_sequence=[self.settings.line_color, self.settings.line_color],
            hover_data={'resistivity': ':.2f Ω⋅m', 'depth': False},  # Add tooltip for resistivity values
            # hover='resistivity'  # Add tooltip for resistivity values
        )
        
        # for i in [0.5, 1, 2]:
        #     z = df['depth']
        #     y = 10+90*(1 / (1 + np.exp(-20.*(z-150)/z.max())))**i
        #     fig.add_scatter(x=y, y=z, line=dict(color='grey'))#, row=1, col=2)

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
        fig.add_shape(type='line', x0=self.rho, x1=self.rho,
                      y0=df['depth'].min(), y1=df['depth'].max(),
                      xref='x1', yref='y1',
                      line=dict(color=self.settings.line_color, dash='dash'),
                      editable=True)

        return fig

    def render(self):
        if not isinstance(self.misfit, list):
            fig = self.render_init()

        elif len(self.misfit) == 0:
            fig = go.Figure()
            fig.update_layout(
                title='Inversion',
                xaxis_title='Iterations',
                yaxis_title='Misfit',
                xaxis_type='linear',  # Resistivity is typically plotted on log scale
                yaxis_type='log',
                yaxis=dict(range=[-1,2]),  # Depth increases downward
                xaxis=dict(range=[-0.1,20.1]),  # Set x-axis range for resistivity
                showlegend=True,
                #modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
            )
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


            # Update layout to match typical resistivity plot conventions
            fig.update_layout(
                title='Inversion',
                xaxis_title='Iterations',
                yaxis_title='Misfit',
                xaxis_type='linear',  # Resistivity is typically plotted on log scale
                yaxis_type='log',
                yaxis=dict(range=[-1,2]),  # Depth increases downward
                xaxis=dict(range=[-0.1,20.1]),  # Set x-axis range for resistivity
                showlegend=True,
                #modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
            )
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
                             dbc.Button("Loose", id='vc_loose_button', color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Medium",id="vc_medium_button",color="primary",outline=True,disabled=True,style={"width": "100%"}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Tight", id='vc_tight_button',color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'30px'}), 
                             html.Div(
                            "Horizontal constraints", style={"fontWeight": "bold", 'textAlign':'center'}),
                            html.Div(style={'height':'10px'}),
                             dbc.Button("Loose", id='hc_loose_button', color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Medium",id="hc_medium_button",color="primary",outline=True,disabled=True,style={"width": "100%"}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Tight", id='hc_tight_button',color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'30px'}),
                             dbc.Button("Starting model", id='reset_inv_model_button', color='secondary', style={'width':'100%'})] , width=2),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                ], style={'height':'100%'})], style={'height':'95%', 'padding':'25px'}),
                html.Div(
                            "Elapsed time: 0:00",
                            id="inv-timer",
                            style={"fontWeight": "bold"}
                        ),
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

           #if not os.path.exists("inversion_log.txt") or os.path.getsize("inversion_log.txt") == 0:
           #     return self.render_init()

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

            # ---- build timer string ----
            timer_text = f"Elapsed time: {int(minutes)}:{int(seconds):02d}"
            if log_time_value is not None:
                timer_text += f" | Last iteration: {log_time_value} s"
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

        

    @classmethod
    def standard(cls, misfit=None, rho=10.):
        return cls(data=misfit, rho=rho)#cls(data=df)

class Single_site(Panel):
    def __init__(self, data,rho=10., **kwargs):
        self.rho = rho
        settings = StartingModelSettings(id='inv-single', **kwargs)
        super().__init__(id='inv-single', settings=settings)
        self.dataframe = data


    def render_init(self):
        
        fig = go.Figure()
        df = pd.DataFrame({
            'resistivity': [self.rho] * 31,  # Default resistivity values
            'depth': np.logspace(0, np.log10(300), 31)  # Example depth values from 0 to 300 meters
            })
        fig = px.line(df,
            x='resistivity',
            y='depth',
            markers=True,
            color_discrete_sequence=[self.settings.line_color, self.settings.line_color],
            hover_data={'resistivity': ':.2f Ω⋅m', 'depth': False},  # Add tooltip for resistivity values
        )

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
        fig.add_shape(type='line', x0=self.rho, x1=self.rho,
                    y0=df['depth'].min(), y1=df['depth'].max(),
                    xref='x1', yref='y1',
                    line=dict(color=self.settings.line_color, dash='dash'),
                    editable=True)

        return fig

    def render(self):

        # fig = px.line(self.dataframe,
        #     x='resistivity',
        #     y='depth',
        #     markers=True,
        #     color_discrete_sequence=[self.settings.line_color, self.settings.line_color],

        # )

        # Update layout to match typical resistivity plot conventions
        fig = go.Figure()
        fig.update_layout(
            title='Inversion',
            xaxis_title='Resistivity [Ω⋅m]',
            yaxis_title='Depth [m]',
            yaxis_type='linear',  # Resistivity is typically plotted on log scale
            xaxis_type='log',
            xaxis=dict(range=[-1,3]),  # Depth increases downward
            yaxis=dict(range=[-0.1,20.1]),  # Set x-axis range for resistivity
            showlegend=True,
            #modebar=dict(remove=['toImage', 'zoom', 'zoomIn', 'zoomOut', 'pan', 'select']),
        )
        return fig
    

    def initialize(self):
        init = html.Div([dbc.Container([
                dbc.Row([
                    dbc.Col(
                        dcc.Graph(figure=self.render_init(), id=self.id, mathjax=True, 
                                    config=dict(edits={'shapePosition':True}, displayModeBar=False)),
                            width=10),
                    dbc.Col([html.Div(
                            "Vertical constraints", style={"fontWeight": "bold", 'textAlign':'center'}),
                            html.Div(style={'height':'10px'}),
                             dbc.Button("Loose", id='vc_sing_loose_button', color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Medium",id="vc_sing_medium_button",color="primary",outline=True,disabled=False,style={"width": "100%"}),
                             html.Div(style={'height':'10px'}),
                             dbc.Button("Tight", id='vc_sing_tight_button',color='secondary', outline=True, disabled=False, style={'width':'100%'}),
                             html.Div(style={'height':'30px'}), 
                             html.Div(style={'height':'10px'}),], width=2),
                             dbc.Tooltip('The sounding panel shows the selected data', target='invert_selected_button')
                ], style={'height':'100%'})], style={'height':'95%', 'padding':'25px'}),
                 gear_maker(self.id)], style={'height': '100%', 'overflow': 'hidden'},
                  )
        return init
    
    def add_callbacks(self, app):
        super().add_callbacks(app)


    @classmethod
    def standard(cls, misfit=None, rho=10.):
        return cls(data=misfit, rho=rho)#cls(data=df)
    


# --------------------- Settings ---------------------
@nosj
class ScatterMapSettings(PanelSettings):
    color: str = '#ff0000'
    highlight_color: str = "#fbff00"
    zoom: int = 10
    png_crs  : str = "EPSG:32637"
    bh_color  : str = "#ffa600"
    # geod = Geod(ellps="WGS84")
    res_min : int = 1
    res_max : int = 300
    res_cmap: str = 'jet'
    # norm = mcolors.LogNorm(vmin=res_min, vmax=res_max)
    # cmap = cm.jet
    line_color : str ="#fbff00"
    radius : int = 50 
    column_width : int = 60
    num_labels_colorbar : int = 4
    id  : str = 'gis'
    # raster_cache_dir = r"C:\Users\au679476\Downloads\test_for_map_pngs_tiffs\raster_cache"
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        print(f"DEBUG SCHEMA KEYS: {self.schema['properties'].keys()}")

from Map_external_layers import ScatterMapRenderer_A, layer_row, make_safe_id_from_stem



class ScatterMapRenderer(Panel):
    def __init__(self, **kwargs):#(self, dataframe, settings, highlighted=None,tiff_path=None,png_path=None,):

        self.dataframe = None
        self.tiff_path = None
        self.png_path = None
        self.tiff_info = None
        self.png_info = None
        self._tiff_cache = {}
        self._png_cache = {}

        settings = kwargs.pop('settings', ScatterMapSettings(id = 'gis'))
        
        super().__init__(id = 'gis', settings=settings)
        
        for key, value in kwargs.items():
            setattr(self, key, value)
            
       
        # Logic previously in __init__
        # if hasattr(self, 'dataframe') and self.dataframe is None:
        #     return 

        self.tiff_info = self._load_tiff() if getattr(self, 'tiff_path', None) else None
        self.png_info = self._load_png() if getattr(self, 'png_path', None) else None

        if self.tiff_info and self.png_info:
            self._check_bounds_match()

  # ------------------------- Render figure -------------------------
    def render(self):
        if not hasattr(self, 'dataframe') or self.dataframe is None: 
            return self.empty_render()
        
        
        color_map = mcolors.LogNorm(vmin=self.settings.res_min, vmax=self.settings.res_max)

        show_google = getattr(self, 'show_google', True)
        show_tiff = getattr(self, 'show_tiff', True)
        show_png = getattr(self, 'show_png', True)
        google_op = getattr(self, 'google_op', True)
        tiff_op = getattr(self, 'tiff_op', True)
        png_op = getattr(self, 'png_op', True)
        show_points = getattr(self, 'show_points', True)
        show_boreholes = getattr(self, 'show_boreholes', True)
        boreholes = getattr(self, 'boreholes', None)
        point_attr = getattr(self, 'point_attr', "none")
        point_filters = getattr(self, 'point_filters', [])
        color_map = getattr(self, 'color_map', {})
        final_line = getattr(self,'final_line', None)
        preview_line = getattr(self,'preview_line', None)
        selected_idx = getattr(self, 'selected_idx', None)
        hover_pt = getattr(self,'hover_pt', None)
        view = getattr(self, 'view', None)
        
        fig = go.Figure()
        if point_attr is None:
                point_attr = "none"

       # --- Decide zoom & center ---
        zoom = view.get("zoom") if view and "zoom" in view else self.settings.zoom
        self.settings.zoom=zoom

        center = view.get("center") if view and "center" in view else self._compute_df_center()
        
        # figure without the points to keep the map on when all points are off
        
        fig = px.scatter_map(
            self.dataframe.iloc[0:0],  # empty base
            lat="latitude",
            lon="longitude",
            color=None,
            zoom=zoom,
            center=center,)
        
        fig.update_layout(
                map=dict(center=center,zoom=zoom),
                showlegend=False,)

        # if self.dataframe is None or self.dataframe.empty:
        #     return None
        is_numeric = False
        
        # if point_filters is None:
        #     point_filters = kwargs.get('point_filters', [])
            
        # if point_attr is None:
        #     point_attr = kwargs.get('point_attr', 'date')
        
        if show_points and self.dataframe is not None:
            display_df = pd.DataFrame() # Default to empty

            if point_attr in self.dataframe.columns and point_filters:
                # Normalize column: string -> no .0 -> stripped
                col_str = self.dataframe[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                
                # Normalize filters: list of strings -> no .0 -> stripped
                if not isinstance(point_filters, list):
                    point_filters = [point_filters]
                clean_fs = [str(f).replace('.0', '').strip() for f in point_filters]
                
                # FILTER: Get rows where column is in our list of clean filters
                display_df = self.dataframe[col_str.isin(clean_fs)]
                    
            # Debug inside renderer
            # print(f"RENDERER: Found {len(display_df)} points for {point_attr}")

            if not display_df.empty:
                # Check if it's one of our numeric columns
                numeric_cols = ['elevation', 'daytime', 'Data Residual', 'DOI']
                is_numeric = point_attr in numeric_cols

                if is_numeric:
                    raw_values = pd.to_numeric(display_df[point_attr], errors='coerce').tolist()
                    hex_colors = get_numeric_colors(raw_values, cmap_name='jet')
                    
                    # 1. Main Trace (The actual dots)
                    fig.add_trace(go.Scattermap(
                        lat=display_df["latitude"],
                        lon=display_df["longitude"],
                        customdata=display_df.index,# for the model plots
                        mode='markers',
                        marker=dict(size=14, opacity=0.8, color=hex_colors), # PURE HEX
                        # name=point_attr,
                        showlegend=True,
                        uid=f"pts_{point_attr}_dots"))
                    
                    # to remove the trace 1 text
                    fig.update_layout(hoverlabel=dict(namelength=0),)

                    # 2. Dummy Trace (Just for the Colorbar)
                    # We put one point at the first location but make it invisible (size 0)
                    colorbar_style = dict(
                        title=dict(
                            text=point_attr, 
                            font = dict(color="black", size=14, family="Arial Black"),
                            side ="top",  # This is the replacement for 'titleside'
                            ),
                        thickness=20,
                        x=1.02,           # Move to the right of the map
                        xanchor="center",   
                        tickfont=dict(color="black", size=11),
                        # White background styling
                        bgcolor="rgba(255, 255, 255, 0.9)", 
                        outlinecolor="white",               
                        outlinewidth=2,
                        len=0.6,          # Makes the bar a bit shorter/neater
                        yanchor="middle",
                        y=0.5             # Centers it vertically
                    )

                    fig.add_trace(go.Scattermap(
                        lat=[display_df["latitude"].iloc[0]],
                        lon=[display_df["longitude"].iloc[0]],
                        mode='markers',
                        marker=dict(
                            size=0, 
                            opacity=0,
                            color=[min(raw_values), max(raw_values)], 
                            colorscale='jet',
                            showscale=True,
                            colorbar=colorbar_style),
                        # name="scale",
                        # hoverinfo='skip',
                        uid=f"pts_{point_attr}_colorbar"))

                else:
                    # Existing categorical logic
                    clean_series = display_df[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

                    for val in clean_fs:
                        # Filter the dataframe for JUST this specific value
                        mask = (clean_series == val)
                        sub_df = display_df[mask]
                        
                        if sub_df.empty:
                            continue
                            
                        # Get the specific color for this value from your color_map
                        trace_color = color_map.get(val, 'grey')

                        # 3. Add a unique trace for every single filter/category
                        fig.add_trace(go.Scattermap(
                            lat=sub_df["latitude"],
                            lon=sub_df["longitude"],
                            mode='markers',
                            marker=dict(
                                size=14,
                                opacity=0.8,
                                color=trace_color,),
                            name=val, 
                            # Unique UID helps Plotly manage transitions
                            uid=f"pts_{point_attr}_{val}",
                            showlegend=True
                        ))
                    pass
            else:
                print("Debug: No points match current filters.")
                
        # --- Add Boreholes ---
        if show_boreholes and boreholes:
            # 'boreholes' here is now the 'bh_projections' list from your other script
            bh_list = boreholes if isinstance(boreholes, list) else [boreholes]
            
            # Extract values from the pre-calculated keys
            bh_lons = [bh['map_lon'] for bh in boreholes] # if 'map_lon' in bh]
            bh_lats = [bh['map_lat'] for bh in boreholes] # if 'map_lat' in bh]
            bh_names = [bh['id'] for bh in boreholes] # if 'map_lon' in bh]

            if bh_lons:
                fig.add_trace(go.Scattermap(
                    lat=bh_lats,
                    lon=bh_lons,
                    mode='markers+text',
                    marker=dict(size=14, color=settings.bh_color, symbol='circle'),
                    text=bh_names,
                    textposition="top right",
                    name="Boreholes",
                    showlegend=False,
                    below='',
                ))

        # --- Highlight ---
        if self.highlighted is not None and show_points:
            df_h = self.dataframe.loc[[self.highlighted]]
            hfig = px.scatter_map(df_h, lat="latitude", lon="longitude")
            hfig.update_traces(marker=dict(size=20, color=self.settings.highlight_color), showlegend=False)
            for tr in hfig.data:
                fig.add_trace(tr)

        final_lines = final_line or []
        preview_line = preview_line or []

        for i, line_coords in enumerate(final_lines):
            # line_coords is now a list like [[lon1, lat1], [lon2, lat2], [lon3, lat3]...]
            if not isinstance(line_coords, (list, tuple)) or len(line_coords) < 2:
                continue

            # Extract all lons and lats for the polyline
            lons = [p[0] for p in line_coords]
            lats = [p[1] for p in line_coords]

            # Highlight selected line in Red, others in Yellow (or your line_color variable)
            is_selected = (i == selected_idx)
            color = "red" if is_selected else "yellow"
            width = 8 if is_selected else 4

            fig.add_trace(
                go.Scattermap( # or go.Scattermap depending on your version
                    lon=lons,
                    lat=lats,
                    mode="lines+markers" if is_selected else "lines", # Markers help see vertices
                    line=dict(color=color, width=width),
                    marker=dict(size=6, color=color) if is_selected else None,
                    below='',
                    name=f"Profile {i+1}",
                    showlegend=False,
                    hoverinfo="name"
                )
            )

        # Add the "Live" Hover Marker
        if hover_pt is not None and isinstance(hover_pt, list):
            fig.add_trace(go.Scattermap(
                lon=[hover_pt[0]],
                lat=[hover_pt[1]],
                mode="markers+text",
                marker=dict(size=15, color="cyan", symbol="circle", opacity=1),
                showlegend=False))
        
        fig.update_layout(
                        map=dict(
                            center=center, 
                            zoom=zoom,
                            style="white-bg", # Ensure style is set here
                            layers=self._build_map_layers(show_google, show_tiff, show_png, google_op, tiff_op, png_op)),
                        margin=dict(r=0, t=0, l=0, b=0),
                        modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
                        # uirevision=f"{kwargs.get('uirevision')}_{point_attr}'",
                        uirevision="keep",
                        dragmode='pan')
        return fig

   
    def initialize(self, initial_rasters=None):
        if initial_rasters is None:
            initial_rasters = getattr(self, "initial_rasters", [])

        # Optional: default layers/opacity so loaded rasters are ON by default
        default_layers = ["google", "points"] 
        default_opacity = {"google": 1.0}
        for r in initial_rasters:
            default_opacity[r["id"]] = r.get("default_opacity", 0.6)
        return html.Div([
            # --- HIDDEN UTILITIES (Triggers & Stores) ---
            # Moving these to the top ensures they exist before any callbacks fire
            html.Div("trigger",id="dummy-output", style={"display": "none"}),
            html.Div(id="test-display"),
            # --- for ctrl + alt + left click and show models  ---
            html.Div(id="window-container", style={"position": "relative", "zIndex": 9999}),
            dcc.Store(id="combined-window-store", data={"window_id": None, "indices": []}),            
            dcc.Store(id="right-click-index-store", data=None),
            dcc.Store(id='active-windows-store', data=[]),
            # --- show a message to the user if line drawn without zoom in---
            dcc.ConfirmDialog(
                                id='zoom-warning-dialog',
                                message='⛔ Drawing Error: Please zoom or pan the map once to initialize the coordinate system before drawing.',
                            ),
            # --- STORES ---
            dcc.Store(id="raster-load-trigger", data=0),
            dcc.Store(id="raster-busy-store", data=False),                       
            dcc.Store(id="raster-registry-store", data=initial_rasters),      # list of loaded rasters
            dcc.Store(id="layers-store", data=default_layers),  # sensible defaults

            dcc.Store(id="opacity-store", data = default_opacity),
            dcc.Store(id="line-preview-store"),
            dcc.Store(id="line-final-store"),
            dcc.Store(id="section-mode-store", data="blocky"),
            dcc.Store(id="map-view-store"),
            dcc.Store(id="selected-line-index", data=0),
            dcc.Store(id="map-hover-marker-store", data=None),
            dcc.Store(id="map-settings-store", data={}), # plot_attribute': 'date', 'color': '#ff0000'
            # dcc.Store(id='global-color-map-store', data=color_master_map),
            # dcc.Store(id="points-available-attrs-store", data=existing_attrs),

            dcc.Store(id="profile-busy-store", data=False),
            dcc.Store(id="profile-load-trigger", data=0),
            dcc.Store(id="profile-last-sig", data=None),  # used to detect changes

            # --- MAIN UI CONTAINER ---
            # html.Div(
            #     id='gis_CB',
            #     style={"height": "250px", "position": "relative", "fontFamily": "sans-serif"},
            #     children=[
                    
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
                                            # layer_row("TIFF", "tiff", default_opacity=0.6),
                                            # layer_row("PNG", "png", default_opacity=0.6),
                                            html.Div(id="dynamic-raster-layer-rows"),
                                            
                                            html.Div([
                                                html.Label("Borehole Data:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
                                                dcc.Checklist(
                                                    id={'type': 'layer-check', 'layer': 'boreholes'}, 
                                                    options=[{'label': ' Show Boreholes', 'value': 'on'}],
                                                    value=[], 
                                                    style={'marginBottom': '15px'}
                                                )
                                            ], id='borehole-toggle-container', style={'display': 'block'}#if (bh_data and len(bh_data) > 0) else 'none'}
                                            ),
                                            html.Div([
                                                layer_row("Points", "points", checked=True, default_opacity=1),
                                                html.Div(
                                                    id="points-submenu-container",
                                                    children=[
                                                        html.Label("Attribute:", style={"fontWeight": "bold", "fontSize": "11px"}),
                                                        dcc.Dropdown(id="points-attr", clearable=False, style={"marginBottom": "10px", "color": "black"}),
                                                        html.Label("Filter:", style={"fontWeight": "bold", "fontSize": "11px"}),
                                                        dcc.Checklist(
                                                            id="points-filter",
                                                            style={"maxHeight": "150px", "overflowY": "auto", "border": "1px solid #f9f9f9"},
                                                        ),
                                                        dcc.Store(id="points-color-map-store", data={}),
                                                        dcc.Store(id="points-filters-by-attr-store", data={}),
                                                    ],
                                                    style={"paddingLeft": "25px", "marginTop": "5px", "fontSize": "12px", "borderLeft": "2px solid #eee"},
                                                ),
                                            ]),
                                        ],
                                    ),
                                ],
                            ),

                            # --- Section Mode Button ---
                            html.Div(
                                style={"position": "relative"},
                                children=[
                                    html.Button("Section ▼", id="section-toggle", style={"padding": "5px 10px"}),
                                    html.Div(
                                        id="section-panel",
                                        style={"display": "none", "position": "absolute", "background": "white", "padding": "8px", "borderRadius": "6px", "boxShadow": "0 2px 6px rgba(0,0,0,0.25)", "marginTop": "4px", "minWidth": "140px"},
                                        children=[
                                            html.Div("Interpolated", id={"type": "section-option", "mode": "interp"}, style={"padding": "6px", "cursor": "pointer"}),
                                            html.Div("Blocky", id={"type": "section-option", "mode": "blocky"}, style={"padding": "6px", "cursor": "pointer"}),
                                            html.Div("Combined", id={"type": "section-option", "mode": "combined"}, style={"padding": "6px", "cursor": "pointer"}),
                                        ],
                                    ),
                                ]
                            ),

                            # --- Lines Mode Button ---
                            html.Div(
                                style={"position": "relative"},
                                children=[
                                    html.Button("Lines ▼", id="profiles-toggle", style={"padding": "5px 10px"}),
                                    html.Div(
                                        id="profiles-panel",
                                        style={"display": "none", "position": "absolute", "background": "white", "padding": "12px", "marginTop": "6px", "borderRadius": "6px", "boxShadow": "0 2px 8px rgba(0,0,0,0.3)", "width": "280px"},
                                        children=[
                                            html.Div("Active Profiles", style={"fontWeight": "bold", "marginBottom": "8px", "fontSize": "13px"}),
                                            html.Div(id="profile-list-container", style={"maxHeight": "250px", "overflowY": "auto", "marginBottom": "10px", "border": "1px solid #eee", "borderRadius": "4px"}),
                                            html.Hr(style={"margin": "10px 0", "border": "0", "borderTop": "1px solid #eee"}),
                                            html.Div(
                                                style={"display": "flex", "gap": "8px"},
                                                children=[
                                                    html.Button("Clear Selected", id="clear-selected-btn", style={"fontSize": "11px", "flex": 1, "padding": "5px", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}),
                                                    html.Button("Clear All", id="clear-all-btn", style={"fontSize": "11px", "flex": 1, "padding": "5px", "color": "red", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}),
                                                ]
                                            )
                                        ]
                                    ),
                                ]
                            ),
                        ],
                    ),                  
                    
                    # ---- MAIN CONTENT ROW: MAP (left) + PROFILE (right) ----
                    html.Div(
                        style={
                            "position": "absolute",
                            "top": "70px",      # start below the toolbar
                            "left": "0",
                            "right": "0",
                            "bottom": "0",             # fill to bottom of screen
                            "display": "flex",
                            "gap": "10px",
                            "padding": "10px",
                            "boxSizing": "border-box",
                            "minHeight": 0,            # important for flex + Graph height
                        },
                        children=[
                            # ================= LEFT: MAP =================
                            html.Div(
                                id="map-wrapper",
                                style={
                                    "flex": "1",
                                    "position": "relative",
                                    "minHeight": 0,
                                    "borderRadius": "8px",
                                    "overflow": "hidden",
                                },
                                children=[
                                    dcc.Graph(
                                        # figure=self.render(),
                                        id='gis-graph',
                                        style={"height": "100%", "width": "100%"},
                                        config={"scrollZoom": True},
                                    ),
                                    html.Div(
                                        id="raster-busy-overlay",
                                        children="Waiting for .tiff cache...",
                                        style={
                                            "display": "none",
                                            "position": "absolute",
                                            "top": "12px",
                                            "right": "12px",
                                            "padding": "6px 10px",
                                            "background": "rgba(0,0,0,0.75)",
                                            "color": "white",
                                            "borderRadius": "6px",
                                            "zIndex": 999999,
                                            "fontSize": "12px",
                                            "pointerEvents": "none",
                                        },
                                    ),
                                ],
                            ),

                            # ================= RIGHT: PROFILE =================
                        
                           html.Div(
                                    id="profile-plot-container",
                                    style={
                                        "flex": "1", "position": "relative", "minHeight": 0,
                                        "background": "white", "borderRadius": "8px",
                                        "boxShadow": "0 0 10px rgba(0,0,0,0.15)", "padding": "5px",
                                        "display": "flex", "flexDirection": "column", "overflow": "hidden",
                                    },
                                    children=[
                                        # 1. THE OVERLAY (Now outside the content div)
                                        html.Div(
                                            "Preparing profile...",
                                            id="profile-busy-overlay",
                                            style={
                                                "display": "none", # Hidden by default
                                                "position": "absolute", "top": "120px", "left": "12px", "right": "auto",
                                                "padding": "6px 15px", "background": "rgba(0,0,0,0.8)",
                                                "color": "white", "zIndex": 9999, "borderRadius": "6px"
                                            }
                                        ),

                                        # 2. THE CONTENT AREA (This is what the callback targets)
                                        html.Div(
                                            id="profile-plot-content", 
                                            style=
                                            {"flex": "1",
                                            "width": "100%", "height": "100%",
                                            "justifyContent": "center",
                                            "alignItems": "center"},
                                            children=[dcc.Graph(id="profile-plot_main", #figure=go.Figure(),
                                                                figure={
                                                                        "data": [],
                                                                        "layout": {
                                                                            "plot_bgcolor": "red",
                                                                            "paper_bgcolor": "white",
                                                                            "template": "none",
                                                                            "xaxis": {"visible": False, "showgrid": False, "zeroline": False},
                                                                            "yaxis": {"visible": False, "showgrid": False, "zeroline": False},
                                                                            "margin": {"t": 0, "b": 0, "l": 0, "r": 0},
                                                                            "annotations": [{
                                                                                "text": "Select or draw a line to generate a profile",
                                                                                "showarrow": False,
                                                                                "font": {"size": 16, "color": "gray"}
                                                                            }]
                                                                        }
                                                                    },
                                                                style={ "height": "100%", "width": "100%", "background": "white", "borderRadius": "8px", "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)" }
                                                                )]
                                        )
                                    ]
                                )
                        
                        
                        ],
                    ), gear_maker(self.id)
           
        ])
    