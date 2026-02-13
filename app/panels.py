from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table, ctx
import numpy as np
from nosj import nosj

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
pio.templates["custom"] = custom_template
pio.templates.default = "custom"

@nosj
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

    def add_callbacks(self, app):
        super().add_callbacks(app)

        @app.callback(
            Output(self.id, "figure", allow_duplicate=True),
            Input("selected-site-id", "data"),
            prevent_initial_call=True
        )
        def update_highlight(site_id):
            if site_id is None:
                raise PreventUpdate

            self.highlighted = site_id
            return self.render()

        



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
   


class rhoaSounding(dbdtSounding):
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

    def compare_synthetic(self):

        y_axis                                             = 'dbdt_syn'

        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['rhoa'] = self.to_rhoa(df_tmp['time'].values(), df_tmp['dbdt'].values())
        df_tmp['rhoa_syn'] = self.to_rhoa(df_tmp['time'].values(), df_tmp['dbdt_syn'].values())
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto'])
        df_tmp.loc[df_tmp['site_id'] == -1, 'include']  = False


        df_tmp['system_id']                                = df_tmp['system_id'].map({1: 'hm', 0: 'lm'})

        error_ub,error_lb = 'error_ub', 'error_lb'
        # if True:
        #     error_ub = None
        #     error_lb = None
        
        fig = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='rhoa',
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            title="Apparent Resistivity",
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
            y='rhoa',
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
            y='rhoa_syn',
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
        df_tmp['rhoa'] = self.to_rhoa(df_tmp['time'].values, df_tmp['dbdt'].values)
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
            y='rhoa',
            color_discrete_sequence=["gray", "gray"],
            color="system_id",
            title="Apparent Resistivity",
            custom_data=["system_id", "data_id", "site_id"],
            error_y=error_ub,
            error_y_minus=error_lb
        )

        df_tmp.loc[df_tmp['site_id'] == -1, 'include'] = True
        df_tmp.loc[(~df_tmp['include']), 'dbdt'] = np.nan


        
        fig2 = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='rhoa',
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
            y='rhoa',
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
                title="1D Resistivity Profile",
            )
        else:
            fig = go.Figure(layout=dict(title="1D Resistivity Profile"))
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
            # fig.add_trace(
            #     go.Scatter(
            #         x=df_layers_long["resistivity"],
            #         y=df_layers_long["depth"],
            #         mode="lines",
            #         line=dict(color='gray'),
            #         name='All Sites'
            #     ), 
            # )



        # Reverse y-axis so depth increases downward
        # fig.update_yaxes(autorange="reversed")
        # fig.update_xaxes(type="log", range=[np.log10(self.settings.rho_min), np.log10(self.settings.rho_max)])
        fig.update_xaxes(title_text='Resistivity [Ω⋅m]',type='log',range=[0, 2.7],showline=True,mirror=True           )

        fig.update_yaxes(
            title_text='Depth [m]',
            range=[180, -0.5],  # depth increasing downward
            showline=True,
            mirror=True,
        )
        return fig        
    
@nosj
class ModelSectionSettings(PanelSettings):
    z: Literal['depth', 'elevation'] = 'depth'
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude', 'distance'] = 'site_id'

class ModelSection(Panel):
    highlighted: int = None
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
            zmin=0,#heatmap_df.min().min(),
            zmax=2.7,#heatmap_df.max().max(),
        )
        fig.update_layout(
            coloraxis_colorbar=dict(
                tickvals = [0, 1, 2, np.log10(500)],
                ticktext = ["1", "10", "100", "500"],
                orientation="h",     # horizontal
                y=-0.45,              # move below plot
                x=0.5,               # center horizontally
                xanchor="center",
                len=0.5,
                thickness = 10,
                title=dict(
            text="Resistivity [Ωm]",
            side="bottom"))
        )
        fig.update_layout(
            xaxis=dict(
                title_standoff=4   # default is ~15–20
            )
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
        legend=dict(x=0.89, y=0.2,xanchor="left",yanchor="top",bgcolor="rgba(255,255,255,0.8)")
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
                    [y_max+50],
                    doi_df["doi"].values,
                    [y_max+50],
                    [y_max+50]
                ]),
                fill="toself",
                fillcolor="rgba(255,255,255,0.6)",
                line=dict(width=0),
                hoverinfo="skip",
                name="Below DOI",
            )
        )

        if self.highlighted is not None and self.dataframe is not None:

            # Get x coordinate of selected site
            selected_df = df_layers_long[df_layers_long["site_id"] == self.highlighted]

            if not selected_df.empty:

                x_value = selected_df[self.settings.x_axis].iloc[0]

                # Width of highlight box
                dx = 0.5  # adjust depending on spacing

                fig.add_shape(
                    type="rect",
                    x0=x_value - dx,
                    x1=x_value + dx,
                    y0=df_layers_long["depth"].min(),
                    y1=df_layers_long["depth"].max()+20,
                    line=dict(color="rgba(0,0,0,0.5)", width=1.5),
                    fillcolor="rgba(0,0,0,0.0)",
                    layer="above"
                )
        fig.update_yaxes(
            range=[doi_df["doi"].max()+8, y_min-8],
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
 