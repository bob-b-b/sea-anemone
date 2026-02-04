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
        id = kwargs.pop('id', 'map')
        settings = MapSettings(id=id, **kwargs)
        super().__init__(id=id, settings=settings)
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

@nosj
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
