import numpy as np
from dash import Dash, dcc, html
import dash_leaflet as dl
import dash_leaflet.express as dlx
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

import json

# Initialize the Dash app
app = Dash(__name__)


import usf

loc_files  = usf.find_location_files("C:/Users/au646858/Downloads/2025_0225")
loc_files += usf.find_location_files("C:/Users/au646858/Downloads/2025_0226")
loc_files += usf.find_location_files("C:/Users/au646858/Downloads/2025_0227")

coordinates = []
for loc_file in loc_files:
    coordinates += usf.get_coordinates(loc_file)
    



lats = np.array([lat for lat, lon in coordinates])
lons = np.array([lon for lat, lon in coordinates])


import usf

lm,hm = usf.Sweep.from_usf("C:/Users/au646858/Downloads/2025_0227/USF_Files_dawa river/L001_S001_2025_0227_120804.usf")

import plotly.graph_objects as go

fig = go.Figure()



# Combined data
fig.add_trace(go.Scatter(x=hm.time.mean(0), y=hm.data.mean(0), mode='lines+markers', name='High Mass Mean Combined', showlegend=False))
fig.add_trace(go.Scatter(x=lm.time.mean(0), y=lm.data.mean(0), mode='lines+markers', name='Low Mass Mean Combined', showlegend=False))

fig.update_layout(
    xaxis_type="log",
    yaxis_type="log",
    title="USF Data",
    xaxis_title="Time",
    yaxis_title="Data",
    template="plotly_white"
)

# Define the layout of the app
ge_url = 'http://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}'
app = Dash(external_stylesheets=[dbc.themes.CYBORG])

app.layout = dbc.Container([
    html.Br(),
    dbc.Row([
        dbc.Col(
            dl.Map([
                dl.TileLayer(url=ge_url),
                dl.LayerGroup([dl.CircleMarker(center=coord, radius=1, color='blue', fill=True, fillColor='blue', fillOpacity=1) for coord in coordinates])
            ], center=[np.mean(lats), np.mean(lons)], zoom=14, style={'height': '80vh'})
        ),
        dbc.Col(dcc.Graph(figure=fig), width=6)
    ])
], fluid=True)




# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)