from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table, ctx, no_update
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

def cdist(lat1,lon1,lat2,lon2):
    lat1rad = lat1/(180./np.pi)
    lon1rad = lon1/(180./np.pi)
    lat2rad = lat2/(180./np.pi)
    lon2rad = lon2/(180./np.pi)
    d = 3963. * np.arccos((np.sin(lat1rad)*np.sin(lat2rad))+ \
            np.cos(lat1rad)*np.cos(lat2rad)*np.cos(lon2rad-lon1rad)) * \
            1.609344 * 1000.
    return d


@nosj
class MapSettings(PanelSettings):
    zoom: int = 14
    color: str = '#ff0000'
    highlight_color: str= '#ffff00'  # Default highlight color
    plot_by: str = 'misfit'
    buffer_color: str= '#0000ff'  # Default buffer color



class Map(Panel):
    dataframe: None
    highlighted: int = None
    buffer_sites: list = None
    view  = None
    lines = None

    def __init__(self, data, **kwargs):
        settings = MapSettings(id='map', **kwargs)
        super().__init__(id='map', settings=settings)
        self.dataframe = data

    def render(self):
        if self.dataframe is None: return self.empty_render()
        df_plot = self.dataframe
        # if 'site_id' in df_plot.columns:
            # df_plot = df_plot[df_plot['site_id'] != -1]

        zoom = self.view['map.zoom'] if self.view is not None else self.settings.zoom
        center = self.view['map.center'] if self.view is not None else None
        from __main__ import sesh
        # if sesh.models is not None:
        if sesh.models is not None and self.settings.plot_by in sesh.models.columns:
            # fig = px.scatter_map(sesh.models, lat="latitude", lon="longitude", zoom=zoom, center=center, 
            #                      color=self.settings.plot_by, color_continuous_scale='turbo'
            #                      )
            fig = px.scatter_map(
                sesh.models,
                lat="latitude",
                lon="longitude",
                zoom=zoom,
                center=center,
                color=self.settings.plot_by,
                color_continuous_scale='turbo',
                custom_data=["site_id"]   # <-- ADD THIS
            )
            fig.update_layout(
                coloraxis_colorbar=dict(
                    orientation="h", 
                    y=-0.01,
                    x=0.5,          
                    xanchor="center",
                    yanchor="top",
                    len=0.75,
                    thickness = 10,
                    title=dict(
                text='',
                side="bottom"))
            )
        else:
            # fig = px.scatter_map(df_plot, lat="latitude", lon="longitude", zoom=zoom, center=center, color_discrete_sequence=[self.settings.color])
            fig = px.scatter_map(
                df_plot,
                lat="latitude",
                lon="longitude",
                zoom=zoom,
                center=center,
                color_discrete_sequence=[self.settings.color],
                custom_data=["site_id"]   # <-- ADD THIS
            )
            
        if self.buffer_sites is not None and len(self.buffer_sites) > 0 and self.dataframe is not None and 'site_id' in self.dataframe.columns:
            df_buffer = self.dataframe[self.dataframe["site_id"].isin(self.buffer_sites)]

            if not df_buffer.empty:
                buffer_trace = px.scatter_map(
                    df_buffer,
                    lat="latitude",
                    lon="longitude",
                    zoom=zoom, center=center, 
                    # color_discrete_sequence=["#00cc96"],  # soft green
                )

                buffer_trace.update_traces(
                    marker=dict(size=12, color=self.settings.buffer_color),
                    name="Buffer window"
                )

                for trace in buffer_trace.data:
                    fig.add_trace(trace)
                fig.data = (fig.data[1], fig.data[0])
        
        fig.update_layout(map_style="white-bg",
            map_layers=[
                {
                    "below": 'traces',
                    "sourcetype": "raster",
                    "sourceattribution": "Google Earth (C)",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }])
        if self.highlighted is not None:
            print('in panels', self.highlighted)
            # highlight_trace = px.scatter_map(df_plot[df_plot.index == self.highlighted], lat="latitude", lon="longitude", zoom=zoom, center=center, color_discrete_sequence=[self.settings.highlight_color])
            
            highlight_trace = px.scatter_map(
                df_plot[df_plot['site_id'] == self.highlighted],
                lat="latitude",
                lon="longitude",
                zoom=zoom,
                center=center,
                color_discrete_sequence=[self.settings.highlight_color],
                custom_data=["site_id"]   # <-- ADD THIS
            )
            highlight_trace.update_traces(marker=dict(size=14))
            for trace in highlight_trace.data:
                fig.add_trace(
                    trace
                )
        if self.lines is not None:
            fig2 = px.line_map(self.lines, lat='latitude', lon='longitude', line_group='line', color='line', zoom=zoom, center=center, hover_name='line')
            fig = go.Figure(data=fig2.data+fig.data, layout=fig.layout)

        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                        modebar=dict(add=['drawline'], remove=['zoomIn', 'zoomOut']),
                        newshape=dict(line_color='cyan', line_width=3, line_dash='dash'),
                        dragmode='select', showlegend=False)
        
        return fig    
    
    @property
    def lat0(self):
        return min([p[1] for p in self.view['map._derived']['coordinates']])
    @property
    def lat1(self):
        return max([p[1] for p in self.view['map._derived']['coordinates']])
    @property
    def lon0(self):
        return min([p[0] for p in self.view['map._derived']['coordinates']])
    @property
    def lon1(self):
        return max([p[0] for p in self.view['map._derived']['coordinates']])
        
    def paper2latlon(self, x, y):
        if self.view is None:
            raise Warning("no view, please zoom")
        elif self.view['map.bearing']!=0 or self.view['map.pitch']!=0:
            raise Warning("no view, please zoom")
        else:
            lat = self.lat0 + (self.lat1-self.lat0)*y
            lon = self.lon0 + (self.lon1-self.lon0)*x
            return lat,lon

    # def initialize(self):
    #     return  html.Div([
    #                 html.Div([
    #                     dcc.Graph(figure=self.render(), id=self.id, mathjax=True,
    #                                 style={'height': '75vh', 'width': '100%','margin':'1%'}),
    #                     dbc.Select(
    #                         options=['misfit', 'doi', 'date'],
    #                         id=self.id+'_plot_by',
    #                         value='misfit',
    #                         style={'margin-left':'45%', 'justify': 'center','width':'10%'}),
    #                 ]),
    #                 gear_maker(self.id)],
    #                 style={'height': '100%'} 
                # )
    def initialize(self):
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(   # 👈 padding wrapper
                            dcc.Graph(
                                figure=self.render(),
                                id=self.id,
                                mathjax=True,
                                style={
                                    'height': '100%',
                                    'width': '100%'
                                }
                            ),
                            style={
                                'flex': '1',
                                'minHeight': 0,
                                'padding': '15px',     # ✅ safe margin
                                'boxSizing': 'border-box'
                            }
                        ),

                        dbc.Select(
                            options=['misfit', 'doi', 'date'],
                            id=self.id+'_plot_by',
                            value='misfit',
                            style={
                                'position': 'absolute',
                                'top': '15px',
                                'left': '50%',
                                'transform': 'translateX(-50%)',
                                'width': '150px'
                            }
                        ),
                    ],
                    style={
                        'flex': '1',
                        'minHeight': 0,
                        'position': 'relative',
                        'display': 'flex'
                    }
                ),
                gear_maker(self.id)
            ],
            style={
                'display': 'flex',
                'flexDirection': 'column',
                'height': '100%',
                'minHeight': 0
            }
        )

    def add_callbacks(self, app):
        super().add_callbacks(app)


        @app.callback(
            self.output,
            Input(self.id+'_plot_by', 'value'),
            prevent_initial_call=True
        )
        def update_plotby(value):
            from __main__ import sesh
            if sesh.models is None:
                raise PreventUpdate
            if value not in sesh.models.columns:
                raise PreventUpdate
            self.settings.plot_by = value
            return self.render()  

        @app.callback(
            Output('map', 'relayoutData'),
            self.output,
            Input('map', 'relayoutData'),
            prevent_initial_call=True
        )
        def update_view(relayout_data):
            fig=no_update
            if 'map.center' in relayout_data:
                self.view = relayout_data
            elif 'shapes' in relayout_data:
                lat0,lon0 = self.paper2latlon(relayout_data['shapes'][-1]['x0'], relayout_data['shapes'][-1]['y0'])
                lat1,lon1 = self.paper2latlon(relayout_data['shapes'][-1]['x1'], relayout_data['shapes'][-1]['y1'])
                line_id = 1
                if self.lines is None:
                    self.lines = pd.DataFrame({'latitude':[lat0], 'longitude':[lon0], 'line':[line_id]})
                else:
                    lat,lon,line_id = self.lines.loc[len(self.lines)-1].tolist()
                    if cdist(lat,lon, lat0, lon0) > 10:
                        line_id +=1 
                        self.lines.loc[len(self.lines)] = [lat0, lon0, line_id]
                self.lines.loc[len(self.lines)] = [lat1, lon1, line_id]
                del relayout_data['shapes']
                fig=self.render()
            return relayout_data, fig



@nosj
class dbdtSoundingSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#2D81FF'
    lm_factor: float = 20.0
    hm_factor: float = 1.0
    plot_error: bool = False
    x_axis: Literal['time', 'gate_id'] = 'time'  # or 'site_id', 'longitude', 'latitude'
    dbdt_max: float = -3
    dbdt_min: float = -12

class dbdtSounding(Panel):
    dataframe = None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSoundingSettings(id='sounding'))
        super().__init__(id='sounding', settings=settings)
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        # if self.dataframe is not None:
        #     self.settings.dbdt_min = np.abs(self.dataframe['dbdt'].values).min()
        #     self.settings.dbdt_max = np.abs(self.dataframe['dbdt'].values).max()

    def compare_synthetic(self):

        y_axis                                             = 'dbdt_syn'

        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto'])
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt_syn']  *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt_syn']  *= self.settings.hm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] == -1, 'include']  = False
        df_tmp.loc[df_tmp['dbdt']<=0, 'dbdt'] = np.nan

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
            error_y_minus=error_lb,
            # range_y=[self.settings.dbdt_min, self.settings.dbdt_max]

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
            # range_y=[self.settings.dbdt_min, self.settings.dbdt_max]

        )

        fig2 = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt_syn',
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id", "site_id"],
            # range_y=[self.settings.dbdt_min, self.settings.dbdt_max]

        )



        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)

        # fig.update_layout(yaxis_range=[self.settings.dbdt_min, self.settings.dbdt_max])


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
            error_y_minus=error_lb,
            range_y=[self.settings.dbdt_min, self.settings.dbdt_max]
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
            range_y=[self.settings.dbdt_min, self.settings.dbdt_max]
        )

        fig3 = px.line(
            df_tmp,
            x=self.settings.x_axis,
            y='dbdt',
            color="system_id",
            color_discrete_sequence=[self.settings.hm_color, self.settings.lm_color],
            title="dbdt vs time by site_id",
            custom_data=["system_id", "data_id", "site_id"],
            range_y=[self.settings.dbdt_min, self.settings.dbdt_max]
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
            yaxis_range=[self.settings.dbdt_min, self.settings.dbdt_max],
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
        self.settings.dbdt_min = 0
        self.settings.dbdt_max = 3


    def compare_synthetic(self):

        y_axis                                             = 'rhoa'

        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['rhoa'] = self.to_rhoa(df_tmp['time'].values, np.abs(df_tmp['dbdt'].values))
        df_tmp['rhoa_syn'] = self.to_rhoa(df_tmp['time'].values, np.abs(df_tmp['dbdt_syn'].values))
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
        df_tmp.loc[(~df_tmp['include']), 'rhoa']       = np.nan
        df_tmp.loc[(~df_tmp['include']), 'rhoa_syn']   = np.nan


        
        fig3 = px.scatter(
            df_tmp,
            x=self.settings.x_axis,
            y='rhoa',
            color_discrete_sequence=["black", "black"],
            color="system_id",
            title="rhoa vs time",
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
            title="rhoa vs time",
            custom_data=["system_id", "data_id", "site_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)

        return fig    

    def observed_only(self):

        y_axis                                             = 'rhoa_syn'
        df_tmp                                             = self.dataframe.sort_values(['site_id', 'system_id',  self.settings.x_axis])
        df_tmp['rhoa'] = self.to_rhoa(df_tmp['time'].values, np.abs(df_tmp['dbdt'].values))
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto']).astype(bool)
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
        df_tmp.loc[(~df_tmp['include']), 'rhoa'] = np.nan


        
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

    def render(self):
        fig = super().render()

        fig.update_layout(
            yaxis_type="log",
            yaxis_range=[self.settings.dbdt_min, self.settings.dbdt_max],
            xaxis_type="log" if self.settings.x_axis == 'time' else "linear",
            xaxis_title=self.settings.x_axis,
            yaxis_title="$\\rho_a$ \\[ $\\Omega$-m\\]",
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
    x_axis: Literal['daytime', 'site_id', 'longitude', 'latitude', 'distance'] = 'site_id'
    y_axis: str = 'dbdt_syn'
    plot_disabled: bool = True
    dbdt_max: float = -3
    dbdt_min: float = -12

class dbdtSection(Panel):
    dataframe = None
    highlighted: int = None
    buffer_start: int = 0
    buffer_len: int = 50

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
        df_tmp['system_id']                                = df_tmp['system_id'].map({1: 'hm', 0: 'lm'})

        # x_axis = df_tmp[self.settings.x_axis].unique()#.values
        # if self.settings.x_axis == 'site_id':
        #     x_axis = x_axis[x_axis>-1]
        # xmin,xmax = np.nanmin(x_axis), np.nanmax(x_axis)

        x_vals = np.sort(df_tmp[self.settings.x_axis].unique())

        if self.settings.x_axis == 'site_id':
            x_vals = x_vals[x_vals > -1]

        n_sites = len(x_vals)

        plot_start = max(0, self.buffer_start)
        plot_end   = min(n_sites, self.buffer_start + self.buffer_len)

        x_slice = x_vals[plot_start:plot_end]

        if len(x_slice) > 0:
            xmin = x_slice.min()
            xmax = x_slice.max()
        else:
            xmin = x_vals.min()
            xmax = x_vals.max()

        dx = xmax - xmin

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
            color_discrete_sequence=[self.settings.lm_color, self.settings.hm_color],
            title="field data versus simulated data",
            custom_data=["system_id", "data_id", "site_id"],
        )

        for trace in fig3.data:
            fig.add_trace(trace)

        for trace in fig2.data:
            fig.add_trace(trace)
        dx = xmax - xmin
        fig.update_xaxes(range=[xmin-0.01*dx, xmax+0.01*dx])
        return fig    

    def observed_only(self):
        y_axis                                             = self.settings.y_axis
        df_tmp = self.dataframe[self.dataframe['gate_id']>-1]
        df_tmp                                             = df_tmp.sort_values(['gate_id', self.settings.x_axis])
        df_tmp['include'] = df_tmp['inuse_manual'].astype(bool, copy=False).fillna(df_tmp['inuse_auto']).astype(bool)
        df_tmp.loc[df_tmp['system_id'] == 0, 'dbdt']      *= self.settings.lm_factor
        df_tmp.loc[df_tmp['system_id'] == 1, 'dbdt']      *= self.settings.hm_factor
        df_tmp.loc[df_tmp['site_id'] ==  -1, 'include']  = False
        df_tmp['system_id']                                = df_tmp['system_id'].map({1: 'hm', 0: 'lm'})

        # x_axis = df_tmp[self.settings.x_axis].unique()#.values
        # if self.settings.x_axis == 'site_id':
        #     x_axis = x_axis[x_axis>-1]
        # xmin,xmax = np.nanmin(x_axis), np.nanmax(x_axis)

        x_vals = np.sort(df_tmp[self.settings.x_axis].unique())

        if self.settings.x_axis == 'site_id':
            x_vals = x_vals[x_vals > -1]

        n_sites = len(x_vals)

        plot_start = max(0, self.buffer_start)
        plot_end   = min(n_sites, self.buffer_start + self.buffer_len)

        x_slice = x_vals[plot_start:plot_end]

        if len(x_slice) > 0:
            xmin = x_slice.min()
            xmax = x_slice.max()
        else:
            xmin = x_vals.min()
            xmax = x_vals.max()

        dx = xmax - xmin

        error_ub,error_lb = 'error_ub', 'error_lb'
        if True:
            error_ub = None
            error_lb = None
        buffer_start = self.buffer_start
        buffer_len   = self.buffer_len

        x_values = df_tmp.columns.tolist()
        n_sites  = len(x_values)
        plot_start = max(0, buffer_start)
        plot_end   = min(n_sites, buffer_start + buffer_len)

        x_slice = x_values[plot_start:plot_end]
        
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
        
        fig.update_xaxes(range=[xmin-0.01*dx, xmax+0.01*dx])
        
        return fig  

    def render(self):
        if self.dataframe is None: return self.empty_render()
        if 'dbdt_syn' in self.dataframe.columns:
            fig = self.compare_synthetic()
        else:
            fig = self.observed_only()

        # if self.highlighted is not None and self.dataframe is not None:
        #     # Get x coordinate of selected site
        #     selected_df = self.dataframe[self.dataframe["site_id"] == self.highlighted]
        #     if not selected_df.empty:

        #         x_value = selected_df[self.settings.x_axis].iloc[0]

        #         # Width of highlight box
        #         dx = 0.5  # adjust depending on spacing

        #         fig.add_shape(
        #             type="rect",
        #             x0=x_value - dx,
        #             x1=x_value + dx,
        #             y0=abs(selected_df["dbdt"]).min()*0.5,
        #             y1=selected_df["dbdt"].max()*25,
        #             line=dict(color="rgba(0,0,0,0.8)", width=1.5),
        #             fillcolor="rgba(0,0,0,0.0)",
        #             # hoverinfo="skip",
        #             layer="above"
        #         )
        if self.highlighted is not None and self.dataframe is not None:

            selected_df = self.dataframe[self.dataframe["site_id"] == self.highlighted]

            if not selected_df.empty:

                x_axis = self.settings.x_axis
                x_value = selected_df[x_axis].iloc[0]

                # Compute spacing dynamically
                x_vals = np.sort(self.dataframe[x_axis].dropna().unique())

                if len(x_vals) > 1:
                    diffs = np.diff(x_vals)
                    dx = np.median(diffs) * 0.5
                else:
                    dx = 0.5

                fig.add_shape(
                    type="rect",
                    x0=x_value - dx,
                    x1=x_value + dx,
                    y0=self.dataframe["dbdt"].abs().min() * 0.5,
                    y1=self.dataframe["dbdt"].max() * 25,
                    line=dict(color="rgba(0,0,0,0.8)", width=1.5),
                    fillcolor="rgba(0,0,0,0.0)",
                )
        fig.update_layout(
            yaxis_type="log",
            yaxis_range=[self.settings.dbdt_min, self.settings.dbdt_max],
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
                html.Div(id='output-data-summary', style={'marginTop': '8px'}),
                dbc.Toast(
                    id='upload-toast',
                    header='Upload',
                    is_open=False,
                    dismissable=True,
                    duration=4000,
                    icon='primary',
                    style={'position': 'fixed', 'top': '70px', 'right': '20px', 'zIndex': 2000, 'minWidth': '280px'}
                ),
                html.Br(),
                html.Div(
                    [
                        dbc.Checkbox(
                            id='use-dem',
                            value=False,
                            label='Use DEM (optional)',
                            style={'marginLeft': '5px'}
                        ),
                        html.Div(
                            [
                                dcc.Upload(
                                    id='upload-dem',
                                    children=html.Div([
                                        'DEM: Drag and Drop \n or \n',
                                        html.A('Select DEM File')
                                    ], style={'height': '90px', 'lineHeight': '80px', 'textAlign': 'center'}),
                                    style={
                                        'borderWidth': '2px',
                                        'borderStyle': 'dashed',
                                        'borderRadius': '5px',
                                        'textAlign': 'center',
                                    },
                                    multiple=False,
                                    accept='.tif,.tiff,.asc,.bil,.dem,.xyz',
                                ),
                                html.Div(id='output-dem-upload'),
                                html.Hr(style={'marginTop': '12px', 'marginBottom': '8px'}),
                                html.Div(
                                    [
                                        html.Div('DEM download (WGS84 lon/lat bbox):', style={'fontWeight': '600', 'marginBottom': '6px'}),
                                        html.Div([
                                            html.Div([
                                                html.Label('Source', style={'fontSize': '12px'}),
                                                dcc.Dropdown(
                                                    id='dem-source',
                                                    options=[
                                                        {'label': 'OpenTopography (global)', 'value': 'opentopo'},
                                                        {'label': 'NCEI ETOPO 2022 (global GeoTIFF)', 'value': 'etopo'},
                                                    ],
                                                    value='opentopo',
                                                    clearable=False,
                                                )
                                            ], style={'width': '60%'}),
                                        ], style={'display': 'flex', 'gap': '10px', 'marginBottom': '8px'}),
                                        html.Div(
                                            [
                                                html.Label('OpenTopography API key', style={'fontSize': '12px'}),
                                                dcc.Input(
                                                    id='dem-api-key',
                                                    type='text',
                                                    value='',
                                                    placeholder='Paste API key (required for OpenTopography)',
                                                    list='dem-api-key-list',
                                                    className='form-control',
                                                    style={'width': '100%', 'borderRadius': '6px'}
                                                ),
                                                html.Datalist(id='dem-api-key-list'),
                                                dbc.Button(
                                                    'History ▼',
                                                    id='dem-api-key-history-toggle',
                                                    color='link',
                                                    size='sm',
                                                    style={'padding': '0', 'marginTop': '6px'}
                                                ),
                                                dbc.Collapse(
                                                    html.Div(
                                                        id='dem-api-key-history',
                                                        style={'marginTop': '6px'}
                                                    ),
                                                    id='dem-api-key-history-collapse',
                                                    is_open=False
                                                ),
                                            ],
                                            id='dem-api-key-container',
                                            style={'marginBottom': '8px'}
                                        ),
                                        html.Div([
                                            html.Div([
                                                html.Label('Min lon', style={'fontSize': '12px'}),
                                                dcc.Input(id='dem-bbox-minlon', type='number', placeholder='-180', debounce=True, style={'width': '100%'})
                                            ], style={'width': '24%'}),
                                            html.Div([
                                                html.Label('Min lat', style={'fontSize': '12px'}),
                                                dcc.Input(id='dem-bbox-minlat', type='number', placeholder='-90', debounce=True, style={'width': '100%'})
                                            ], style={'width': '24%'}),
                                            html.Div([
                                                html.Label('Max lon', style={'fontSize': '12px'}),
                                                dcc.Input(id='dem-bbox-maxlon', type='number', placeholder='180', debounce=True, style={'width': '100%'})
                                            ], style={'width': '24%'}),
                                            html.Div([
                                                html.Label('Max lat', style={'fontSize': '12px'}),
                                                dcc.Input(id='dem-bbox-maxlat', type='number', placeholder='90', debounce=True, style={'width': '100%'})
                                            ], style={'width': '24%'}),
                                        ], style={'display': 'flex', 'gap': '6px', 'marginBottom': '8px'}),
                                        html.Div(
                                            [
                                                dbc.Button('Use data extent', id='dem-bbox-from-data', color='secondary', outline=True, size='sm'),
                                            ],
                                            style={'marginBottom': '8px'}
                                        ),
                                        html.Div([
                                            html.Div([
                                                html.Label('Resolution', style={'fontSize': '12px'}),
                                                dcc.Dropdown(
                                                    id='dem-resolution',
                                                    options=[
                                                        {'label': 'Global Copernicus GLO-30 (~30 m)', 'value': 'opentopo_cop30'},
                                                        {'label': 'Global SRTMGL1 (~30 m)', 'value': 'opentopo_srtmgl1'},
                                                        {'label': 'Global SRTMGL3 (~90 m)', 'value': 'opentopo_srtmgl3'},
                                                        {'label': 'Global ALOS (~30 m)', 'value': 'opentopo_alos'},
                                                        {'label': 'ETOPO2022 30 arc-second (surface, global)', 'value': 'etopo_30s'},
                                                        {'label': 'ETOPO2022 60 arc-second (surface, global)', 'value': 'etopo_60s'},
                                                    ],
                                                    value='opentopo_cop30',
                                                    clearable=False,
                                                )
                                            ], style={'width': '60%'}),
                                            html.Div([
                                                dbc.Button(
                                                    'Download DEM',
                                                    id='download-dem',
                                                    color='primary',
                                                    style={'flex': '1', 'height': '42px'}
                                                ),
                                                dbc.Button(
                                                    'Save DEM + KML',
                                                    id='save-dem',
                                                    color='secondary',
                                                    outline=True,
                                                    disabled=True,
                                                    style={'flex': '1', 'height': '42px'}
                                                ),
                                            ], style={'width': '40%', 'display': 'flex', 'gap': '6px', 'marginTop': '18px', 'alignItems': 'flex-start'}),
                                        ], id='dem-resolution-container', style={'display': 'flex', 'gap': '10px', 'alignItems': 'flex-start'}),
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    'Load DEM vs GPS',
                                                    id='load-dem-vs-gps',
                                                    color='secondary',
                                                    outline=False,
                                                    style={'width': '100%', 'backgroundColor': '#7B2CBF', 'borderColor': '#7B2CBF'}
                                                ),
                                            ],
                                            style={'marginTop': '8px'}
                                        ),
                                        html.Div(
                                            [
                                                dbc.Button(
                                                    'Restore GPS elevation',
                                                    id='restore-gps-elevation',
                                                    color='secondary',
                                                    outline=True,
                                                    style={'width': '100%'},
                                                    disabled=True
                                                ),
                                            ],
                                            style={'marginTop': '6px'}
                                        ),
                                        html.Div(id='output-dem-download', style={'marginTop': '6px'}),
                                        html.Div(id='output-dem-save', style={'marginTop': '6px'}),
                                        html.Div(id='output-dem-load', style={'marginTop': '6px'})
                                    ]
                                ),
                            ],
                            id='dem-upload-container',
                            style={'display': 'none', 'marginTop': '10px'}
                        ),
                    ],
                    id='dem-options-container',
                    style={'display': 'none'}
                ),
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
    buffer_len = 50
    buffer_start = 0

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
            heatmap_df = df_layers_long.set_index('site_id').sort_index(ascending=True)
            buffer_start = self.buffer_start
            buffer_len   = self.buffer_len

            x_values = df_layers_long['site_id'].unique().tolist()
            n_sites  = len(x_values)

            plot_start = max(0, buffer_start)
            plot_end   = min(n_sites, buffer_start + buffer_len)

            x_slice = x_values[plot_start:plot_end]

            fig = px.line(
                df_layers_long[df_layers_long['site_id'].isin(x_slice)],
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
    buffer_len = 50
    buffer_start = 0
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

        heatmap_df = df_layers_long.pivot_table(
            index='depth', columns=self.settings.x_axis, values='log_resistivity'
        )        
        heatmap_df = heatmap_df.sort_index(ascending=True)
        buffer_start = self.buffer_start
        buffer_len   = self.buffer_len

        x_values = heatmap_df.columns.tolist()
        n_sites  = len(x_values)

        plot_start = max(0, buffer_start)
        plot_end   = min(n_sites, buffer_start + buffer_len)

        x_slice = x_values[plot_start:plot_end]
        df_layers_long = df_layers_long[df_layers_long[self.settings.x_axis].isin(x_slice)]

        fig = px.imshow(
            heatmap_df[x_slice],
            aspect='auto',
            origin='lower',
            color_continuous_scale='turbo',
            labels={'x': self.settings.x_axis, 'y': 'Depth [m]', 'color': 'Resistivity [Ω·m]'},
            zmin=0,
            zmax=2.7,
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

        # ---- Misfit only for buffered sites ----
        misfit_df = (
            df_layers_long
            .groupby(self.settings.x_axis)['misfit']
            .first()
            .reset_index()
        )

        misfit_trace = go.Scatter(
            x=misfit_df[self.settings.x_axis],
            y=misfit_df['misfit'],
            mode='lines',
            line=dict(color='black', width=2),
            name='Misfit',
            yaxis='y2'
        )

        y_dashed = misfit_df['misfit'].copy()
        y_dashed[y_dashed <= 8] = np.nan
        y_dashed[y_dashed > 8] = 7.95

        fig.add_trace(go.Scatter(
            x=misfit_df[self.settings.x_axis],
            y=y_dashed,
            mode="lines",
            line=dict(color="rgba(0,0,0,0.7)", dash="dash"),
            showlegend=False,
            yaxis='y2'
        ))


        # misfit_trace.update(
        #     yaxis='y2',
        #     line=dict(color='black', width=2),
        #     name='Misfit',showlegend=True
        # )
        # fig.update_layout(yaxis2=dict(range=[0, 8]))
        # fig.add_trace(go.Scatter(
        #     x=x,
        #     y=y_dashed,
        #     mode="lines",
        #     line=dict(color="rgb(0,0,0,0.7)", dash="dash"),
        #     # hoverinfo="skip",
        #     showlegend=False, yaxis='y2'
        # ))



        fig.add_trace(misfit_trace)

        fig.update_layout(
        legend=dict(x=0.89, y=0.2,xanchor="left",yanchor="top",bgcolor="rgba(255,255,255,0.8)")
            )

        fig.update_layout(yaxis2=dict(title=dict(text="Misfit",standoff=10),overlaying="y",side="right",showgrid=False)
)
        doi_df = (df_layers_long.groupby(self.settings.x_axis)["doi"].first().reset_index())
        if not doi_df.empty:
            x_min = min(x_slice)
            x_max = max(x_slice)
            y_max = df_layers_long["depth"].max()

            fig.add_trace(
                go.Scatter(
                    x=np.concatenate([
                        [x_min],
                        doi_df[self.settings.x_axis].values,
                        [x_max],
                        [x_min]
                    ]),
                    y=np.concatenate([
                        [y_max + 50],
                        doi_df["doi"].values,
                        [y_max + 50],
                        [y_max + 50]
                    ]),
                    fill="toself",
                    fillcolor="rgba(255,255,255,0.6)",
                    line=dict(width=0),
                    name="Below DOI",
                )
            )

        if self.highlighted is not None and self.dataframe is not None:

            selected_df = self.dataframe[self.dataframe["site_id"] == self.highlighted]

            if not selected_df.empty:

                x_axis = self.settings.x_axis
                x_value = selected_df[x_axis].iloc[0]

                x_vals = np.sort(self.dataframe[x_axis].dropna().unique())

                if len(x_vals) > 1:
                    diffs = np.diff(x_vals)
                    dx = np.median(diffs) * 0.5
                else:
                    dx = 0.5

                fig.add_shape(
                    type="rect",
                    x0=x_value - dx,
                    x1=x_value + dx,
                    y1=df_layers_long["depth"].min(),
                    y0=df_layers_long["depth"].max()+20,
                    line=dict(color="black", width=1.5),
                    fillcolor="rgba(0,0,0,0.0)",
                )

        fig.update_yaxes(
            range=[doi_df["doi"].max()+8, df_layers_long["depth"].min()-8],
            autorange=False,
            #title="Depth [m]"
        )

        fig.update_xaxes(
            range=[x_min, x_max],
            autorange=False
        )
        fig.update_layout(yaxis2=dict(range=[0, 8]))
        return fig
    # def add_callbacks(self, app):
    #     super().add_callbacks(app)

    #     @app.callback(
    #         Output(self.id, 'figure', allow_duplicate=True),
    #         Output('data-buffer','data', allow_duplicate=True),
    #         Input('next-buffer', 'data'),
    #         Input('prev-buffer', 'data'),
    #         State('buffer','length'),
    #         prevent_initial_call=True
    #     )
    #     def update_buffer(data,length):
    #         if not ctx.triggered:
    #             raise PreventUpdate
    #         trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    #         highlighted = m1.highlighted
    #         if trigger_id == 'next-buffer':
    #             self.buffer_start += length
    #             if self.buffer_start > len(self.dataframe): self.buffer_start-=length 
    #         elif trigger_id == 'prev-buffer':
    #             self.buffer_start -= length
    #             if self.buffer_start>0: self.buffer_start=0
                
    #         return self.render(), {"length": length, "start_site": self.buffer_start}
        
    #     @app.callback(
    #         Output(self.id, 'figure', allow_duplicate=True),
    #         Input('next-buffer', 'data'),
    #         prevent_initial_call=True
    #     )
    #     def update_buffer(data,length):
    #         if not ctx.triggered:
    #             raise PreventUpdate
    #         trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    #         highlighted = m1.highlighted
    #         if trigger_id == 'next-buffer':
    #             self.buffer_start += length
    #             if self.buffer_start > len(self.dataframe): self.buffer_start-=length 
    #         elif trigger_id == 'prev-buffer':
    #             self.buffer_start -= length
    #             if self.buffer_start>0: self.buffer_start=0
    #         return self.render()
    #     return fig


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


class HotKeyReminder(Panel):
    javascript =     """
        function(id) {
            document.addEventListener("keydown", function(event) {
                // Check if focus is on an input element
                const activeElement = document.activeElement;
                const isInputFocused = activeElement && (
                    activeElement.tagName === 'INPUT' || 
                    activeElement.tagName === 'TEXTAREA' || 
                    activeElement.contentEditable === 'true'
                );
                
                if (event.ctrlKey) {
                    if (event.key == 'd') {
                        document.getElementById('disableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'e') {
                        document.getElementById('enableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    
                    if (event.key == 's') {
                        if (event.shiftKey) {
                            document.getElementById('saveAsButton').click()
                        } else {
                            document.getElementById('saveButton').click()
                        }
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }
                
                // Arrow keys without Ctrl, but only if not typing in an input
                if (!isInputFocused) {
                    if (event.key == 'ArrowLeft') {
                        document.getElementById('highlight_prev').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'ArrowRight') {
                        document.getElementById('highlight_next').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }
            });
            return window.dash_clientside.no_update       
        }
    """

    def __init__(self):
        super().__init__(id='processing_buttons')

    def initialize(self):
        x = html.Div([
            # dcc.Markdown(children='### buttons and hot keys'),
            html.Div(
                [
                    dbc.ButtonGroup([
                    dbc.Button("disable [ctrl+d]", id='disableButton'),
                    dbc.Button("enable  [ctrl+e]", id='enableButton'),
                    ]),
                    dbc.ButtonGroup([
                        dbc.Button("Previous buffer [<<-]", id='prev-buffer', style={"marginRight": "6px"}),
                        dbc.Button("Previous [<-]", id='highlight_prev', style={"marginRight": "6px"}),
                        dbc.Button("Next [->]", id='highlight_next', style={"marginRight": "6px"}),
                        dbc.Button("Next buffer [->>]", id='next-buffer', style={"marginRight": "12px"}),
                        html.Div(
                            [
                                html.Small(
                                    "Buffer length:",
                                    style={
                                        "marginLeft": "12px",
                                        "marginRight": "6px",
                                        "color": "#555",
                                        "fontSize": "12px",
                                    }
                                ),
                                dcc.Input(
                                    id='buffer-length-input',
                                    type='number',
                                    min=1,
                                    step=1,
                                    value=50,
                                    style={
                                        "width": "70px",
                                        "height": "32px",
                                        "fontSize": "13px"
                                    }
                                ),
                            ],
                            style={
                                "display": "flex",
                                "alignItems": "center",
                            }
                        )
                    ]),
                    dbc.ButtonGroup([
                        dbc.Button("save [ctrl+s]", id='saveButton'),
                    ])
                ], style={'padding': '10px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}
                ),
                dcc.Location(id='url_button'),
            ]
        , id='processing_buttons')
        return x
    
    def add_callbacks(self, app):
        pass
        # return super().add_callbacks(app)

