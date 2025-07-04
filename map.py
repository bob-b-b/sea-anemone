

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

class Panel:
    def __init__(self, id):
        self.id = id

    def to_nodes(self):
        pass

    