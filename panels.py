from basepanel import *


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
class dbdtSoundingSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#0000ff'

class dbdtSounding(Panel):
    lm_time: None
    lm_data: None
    hm_time: None
    hm_data: None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSoundingSettings(id='sounding'))
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
            margin=dict(t=30),
            dragmode='select'
        )
        return fig



@dataclass
class dbdtSectionSettings(PanelSettings):
    lm_color: str = '#ff0000'
    hm_color: str = '#2D81FF'
    lm_factor: float = 20.0
    hm_factor: float = 1.0

class dbdtSection(Panel):
    lm_time: None
    lm_data: None
    hm_time: None
    hm_data: None


    def __init__(self, **kwargs):
        settings = kwargs.pop('settings', dbdtSectionSettings(id='tTEM'))
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
                    ]),
                    style={
                        'height': '100px',
                        'lineHeight': '100px',
                        'borderWidth': '2px',
                        'borderStyle': 'dashed',
                        'borderRadius': '5px',
                        'textAlign': 'center',
                        'margin': '25px'
                    },
                    multiple=True,
                ),
                html.Div(id='output-data-upload', style={'overflow': 'hidden'}),
            ],
            style={'margin': '10px', 'overflow': 'hidden'}
        )
    
    def initialize(self):
        return html.Div([
            dcc.Markdown("# welcome to sea anemone", style={'textAlign': 'center'}),
            dcc.Markdown("## Upload your data to get started"),
            self.render(),
            gear_maker(self.id)],
            style={'height': '100%', 'overflow': 'hidden', 'margin':'10px'} 
        )    


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
    
    panels = [u1, m1, dbdt1, dbdt2, rhoa1]
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
                        u1.layout_dict,
                        m1.layout_dict,
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



    app.run(port=8050, dev_tools_hot_reload=True)