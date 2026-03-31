from basepanel import *
import plotly.io as pio
from typing import Literal
import plotly.express as px
import plotly.graph_objects as go
from dash import dash_table, ctx, no_update
import numpy as np
from nosj import nosj
import utm
from pandas import DataFrame


line_colors = [
    '#1f77b4',  # muted blue
    '#ff7f0e',  # safety orange
    '#2ca02c',  # cooked asparagus green
    '#d62728',  # brick red
    '#9467bd',  # muted purple
    '#8c564b',  # chestnut brown
    '#e377c2',  # raspberry yogurt pink
    '#7f7f7f',  # middle gray
    '#bcbd22',  # curry yellow-green
    '#17becf'   # blue-teal
]


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


class ProjectionLine:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        dx,dy = x[1]-x[0], y[1]-y[0]
        self.phi = -np.arctan2(dy,dx)
        self.R = np.array([[np.cos(self.phi), -np.sin(self.phi)],
                           [np.sin(self.phi), np.cos(self.phi)]])
        self.iR = np.array([[np.cos(-self.phi), -np.sin(-self.phi)],
                            [np.sin(-self.phi), np.cos(-self.phi)]])

        self.length = np.sqrt(dx**2 + dy**2)
        self.m = dy/dx
        self.b = y[0] - self.m*x[0]

    def inbounds(self, x, y, buffer=np.inf):
        xp,yp = self.to_line_coords(x,y)
        inbounds = (xp>=0) * (xp<=self.length)
        inbounds *= np.abs(yp) <= buffer
        return inbounds
        
    def to_line_coords(self, x, y):
        xt,yt = x-self.x[0], y-self.y[0]
        return np.dot(self.R, np.array([xt,yt]))
    
    def from_line_coords(self, xp, yp):
        xt,yt = np.dot(self.iR, np.array([xp,yp]))
        return xt+self.x[0], yt+self.y[0]
    

    
class Profile:
    def __init__(self, lat, lon):
        x,y,zone,letter = utm.from_latlon(lat, lon)
        self.x = x
        self.y = y
        self.zone = zone
        self.letter = letter
        self.n_segments = len(x)-1
        self.lines = [ProjectionLine(x[i:i+2], y[i:i+2]) for i in range(self.n_segments)]
        self.cumulative_length = np.cumsum([0]+[line.length for line in self.lines])

    @classmethod
    def from_point_list(cls, points):
        x = np.array([point[0] for point in points])
        y = np.array([point[1] for point in points])
        return cls(x,y)
    
    @property
    def length(self):
        return self.cumulative_length[-1]
    
    @property
    def m(self):
        return np.array([line.m for line in self.lines]).squeeze()

    @property
    def b(self):
        return np.array([line.b for line in self.lines]).squeeze()
        
    def inbounds(self, x, y, buffer=np.inf):
        inbounds = np.zeros_like(x, dtype=bool)
        for line in self.lines:
            inbounds += line.inbounds(x,y, buffer=buffer)
        return inbounds

    def to_line_coords(self, x, y, return_segment_index=False):
        if not isinstance(x, np.ndarray): x = np.array([x], dtype=float)
        if not isinstance(y, np.ndarray): y = np.array([y], dtype=float)
        projections = np.zeros((self.n_segments, 2, len(x)))
        projection_dist = np.zeros_like(projections)
        for i,line in enumerate(self.lines):
            projections[i] = line.to_line_coords(x,y)
            projection_dist[i] = projections[i]
            # not in bound points lie beyond the ends of the line segement.
            # There are instances when the extension of a particular line segement gets closer to a point than the line segment that is actually closest to the point. To avoid this, out of bound points get additional perpendicular distance added to them, so the ideal line segment is more likely to get assigned.
            not_inbounds = np.logical_not(line.inbounds(x,y))
            
            projection_dist[i,1,not_inbounds] = np.abs(projection_dist[i,1,not_inbounds]) + np.abs(projections[i,0,not_inbounds])
        idx_min = np.nanargmin(np.abs(projection_dist[:,1:,:]), axis=0)

        projections = idx_min.choose(projections)

        projections[0,:] += np.squeeze(self.cumulative_length[idx_min])
        if return_segment_index:
            return projections[0], projections[1], idx_min[0]
        else:
            return projections[0], projections[1]
    
    
    def from_line_coords(self, xp, yp):
        if isinstance(xp, (int, float)):
            xp, yp = np.array([xp], dtype=float), np.array([yp], dtype=float)
        idx = np.clip(np.searchsorted(self.cumulative_length, xp, side='right')-1, 0, self.n_segments-1)
        x = np.zeros_like(xp)
        y = np.zeros_like(yp)
        for i in range(len(xp)):
            x[i], y[i] = self.lines[idx[i]].from_line_coords(xp[i]-self.cumulative_length[idx[i]], yp[i])
        return x,y
    
    @property
    def line_x(self):
        xp,yp = self.to_line_coords(self.x, self.y)
        return xp
    
    @property
    def line_y(self):
        xp,yp = self.to_line_coords(self.x, self.y)
        return yp
    
    def __call__(self, lat, lon):
        x,y,_,__ = utm.from_latlon(lat, lon, force_zone_number=self.zone, force_zone_letter=self.letter)
        x,y = self.to_line_coords(x,y)
        y[x<0] = np.inf
        y[x>self.length] = np.inf
        return x,y


@nosj
class MapSettings(PanelSettings):
    zoom: int = 10
    color: str = '#ff0000'
    highlight_color: str= '#ffff00'  # Default highlight color
    plot_by: Literal['', 'misfit', 'doi', 'date', '_line_1_x', '_line_1_y'] = ''
    buffer_color: str= "#ffffff"  # Default buffer color
    dragmode: str='select'
    view: dict = None


class Map(Panel):
    dataframe: None
    highlighted: int = None
    buffer_sites: list = None
    lines = None

    def __init__(self, data, **kwargs):
        settings = MapSettings(id='map', **kwargs)
        super().__init__(id='map', settings=settings)
        self.dataframe = data

    def render(self):
        if self.dataframe is None: return self.empty_render()
        df_plot = self.dataframe
        if 'site_id' in df_plot.columns:
            df_plot = df_plot[df_plot['site_id'] != -1]

        zoom = self.settings.view['map.zoom'] if self.settings.view is not None else self.settings.zoom
        center = self.settings.view['map.center'] if self.settings.view is not None else None

        if self.settings.plot_by in self.dataframe.columns:

            fig = px.scatter_map(df_plot, lat="latitude", lon="longitude", zoom=zoom, center=center, 
                                 color=self.settings.plot_by, color_continuous_scale='turbo'
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
            fig = px.scatter_map(df_plot, lat="latitude", lon="longitude", zoom=zoom, center=center, color_discrete_sequence=[self.settings.color])

        if self.buffer_sites is not None and len(self.buffer_sites) > 0 and self.dataframe is not None and 'site_id' in self.dataframe.columns:
            df_buffer = self.dataframe[self.dataframe["site_id"].isin(self.buffer_sites)]

            if not df_buffer.empty:
                buffer_trace = px.scatter_map(
                    df_buffer,
                    lat="latitude",
                    lon="longitude",
                    zoom=zoom, center=center, 
                )

                buffer_trace.update_traces(
                    marker=dict(size=12, color=self.settings.buffer_color),
                    name="Buffer window"
                )

                for trace in buffer_trace.data:
                    fig.add_trace(trace)
                
                fig.data = fig.data[-1:]+fig.data[:-1]

        fig.update_layout(map_style="white-bg",
            map_layers=[
                {
                    "below": 'traces',
                    "sourcetype": "raster",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }])
        if self.highlighted is not None:
            highlight_trace = px.scatter_map(df_plot[df_plot.index == self.highlighted], lat="latitude", lon="longitude", zoom=zoom, center=center, color_discrete_sequence=[self.settings.highlight_color])
            highlight_trace.update_traces(marker=dict(size=14))
            for trace in highlight_trace.data:
                fig.add_trace(
                    trace
                )

        if self.lines is not None and self.settings.dragmode=='drawline':
            for line_id in self.lines.line.unique():
                fig.add_shape(self.line2path(line_id))

        elif self.lines is not None:
            fig2 = px.line_map(self.lines, lat='latitude', lon='longitude', line_group='line', color='line', zoom=zoom, center=center, hover_name='line')
            fig2.update_traces(mode='lines+markers')
            fig = go.Figure(data=fig2.data+fig.data, layout=fig.layout)


        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0},
                          modebar=dict(add=['drawline', 'eraseshape'], remove=['zoomIn', 'zoomOut', 'lasso', 'toImage', 'plotly-logomark']),
                          newshape=dict(line_color='black', line_width=3, line_dash='dash'),
                          dragmode=self.settings.dragmode, showlegend=False)
        
        return fig 

    def line2path(self, line_id):
        c_line = self.lines.loc[self.lines.line==line_id]
        path_dict = {'editable': True, 'type':'path', 'line': {'color': line_colors[int(line_id)%len(line_colors)-1], 'width': 3, 'dash': 'dash'}}
        path = ''
        for i,record in c_line.iterrows():
            cx,cy = self.latlon2paper(record['latitude'], record['longitude'])
            path += f'L{cx},{cy}'
        path_dict['path'] = 'M' + path[1:]
        return path_dict
    
    def path2line(self, path_str):
        points = path_str[1:].split('L')
        lat, lon = [], []
        for point in points:
            cx, cy = map(float, point.split(','))
            plat, plon = self.paper2latlon(cx, cy)
            lat.append(plat)
            lon.append(plon)
        return lat, lon

    @property
    def lat0(self):
        return min([p[1] for p in self.settings.view['map._derived']['coordinates']])
    @property
    def lat1(self):
        return max([p[1] for p in self.settings.view['map._derived']['coordinates']])
    @property
    def lon0(self):
        return min([p[0] for p in self.settings.view['map._derived']['coordinates']])
    @property
    def lon1(self):
        return max([p[0] for p in self.settings.view['map._derived']['coordinates']])
        
    def paper2latlon(self, x, y):
        if self.settings.view is None:
            raise Warning("no view, please zoom")
        elif self.settings.view['map.bearing']!=0 or self.settings.view['map.pitch']!=0:
            raise Warning("non-standard view, bearing and pitch must be zero, reset axis and zoom")
        else:
            lat = self.lat0 + (self.lat1-self.lat0)*y
            lon = self.lon0 + (self.lon1-self.lon0)*x
            return lat,lon
        
    def latlon2paper(self, lat,lon):
        if self.settings.view is None:
            raise Warning("no view, please zoom")
        elif self.settings.view['map.bearing']!=0 or self.settings.view['map.pitch']!=0:
            raise Warning("non-standard view, bearing and pitch must be zero, reset axis and zoom")
        
        x = (lon - self.lon0) / (self.lon1-self.lon0)
        y = (lat - self.lat0) / (self.lat1-self.lat0)
        return x,y

    def initialize(self):
        return html.Div(
            [
                html.Div(
                    [
                        html.Div(  
                            dcc.Graph(
                                figure=self.render(),
                                id=self.id,
                                mathjax=True,
                                responsive=True,
                                style={
                                    'height': '100%',
                                    'width': '100%'
                                }
                            ),
                            style={
                                'flex': '1',
                                'minHeight': 0,
                                'boxSizing': 'border-box',
                                'marginBottom': '50px'
                            }
                        ),

                        dbc.Select(
                            options=self.settings.schema['properties']['plot_by']['enum'],
                            id=self.id+'_plot_by',
                            value=self.settings.plot_by,
                            style={
                                'position': 'absolute',
                                'bottom': '10px',
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
            if value not in self.dataframe.columns:
                raise PreventUpdate
            self.settings.plot_by = value
            return self.render()  

        @app.callback(
            self.output,
            Output('model_section_axis', 'options', allow_duplicate=True),
            Output({'type': f'settings-model_section', 'key': 'x_axis'}, 'options', allow_duplicate=True),
            Input(self.id, 'relayoutData'),
            State('model_section_axis', 'options'),
            prevent_initial_call=True
        )
        def update_view(relayout_data, options):
            from __main__ import sesh
            if 'map.center' in relayout_data:
                self.settings.view = relayout_data
            elif 'dragmode' in relayout_data:
                self.settings.dragmode=relayout_data['dragmode']

            elif 'shapes' in relayout_data:
                if relayout_data['shapes'][-1]['type']=='line':
                    
                    lat0,lon0 = self.paper2latlon(relayout_data['shapes'][-1]['x0'], relayout_data['shapes'][-1]['y0'])
                    lat1,lon1 = self.paper2latlon(relayout_data['shapes'][-1]['x1'], relayout_data['shapes'][-1]['y1'])
                    line_id = 1
                    if self.lines is None:
                        self.lines = DataFrame({'latitude':[lat0], 'longitude':[lon0], 'line':[line_id]})
                    else:
                        lat,lon,line_id = self.lines.loc[len(self.lines)-1].tolist()
                        if cdist(lat,lon, lat0, lon0) > 10:
                            line_id +=1 
                            self.lines.loc[len(self.lines)] = [lat0, lon0, line_id]
                    self.lines.loc[len(self.lines)] = [lat1, lon1, line_id]
                    del relayout_data['shapes']
                    sesh.lines = self.lines.copy()
                    sesh.update_site_table()
                    fig=self.render()
                elif len(relayout_data['shapes'])==len(self.lines.line.unique())-1:
                    saved_paths = [self.line2path(line_id)['path'] for line_id in self.lines.line.unique()]
                    remaining_paths = [shape['path'] for shape in relayout_data['shapes']]
                    for line_id, path in zip(self.lines.line.unique(), saved_paths):
                        if path not in remaining_paths:
                            self.lines = self.lines[self.lines.line!=line_id]
                    sesh.lines = self.lines.copy()
                    sesh.update_site_table()
            else:
                key, value = list(relayout_data.items())[0]
                if key.startswith('shapes[') and key.endswith('].path'):
                    line_id = int(key.split('[')[1].split(']')[0])+1
                    lat, lon = self.path2line(value)
                    self.lines.loc[self.lines.line==line_id, ['latitude', 'longitude']] = np.array([lat, lon]).T
                    sesh.lines = self.lines.copy()
                    sesh.update_site_table()

            if sesh.lines is not None:
                line_ids = sesh.lines['line'].unique()
                line_options = [f'line {line_id:0.0f}' for line_id in line_ids]
                options = line_options + [option for option in options if not option.startswith('line')]
            return self.render(), options, options
