import dash_leaflet as dl
import numpy as np

import usf

import os
usf_folders = [#'/home/matt/geophysics_data/TEM/sTEM_data/2025_0227/USF_Files_dawa river/',
            #    '/home/matt/geophysics_data/TEM/sTEM_data/2025_0226/USF_Files_Dawa River Channel/',
               '/home/matt/geophysics_data/TEM/sTEM_data/2025_0302/USF_Files_dawa river 3/'
               ]

sweeps = []
for usf_folder in usf_folders:
    usf_files = [usf_folder+f for f in os.listdir(usf_folder) if f.endswith('.usf')]
    for usf_file in usf_files:        
        sweeps += usf.Sweep.from_usf(usf_file, combine=False)
points = set([x.points for x in sweeps])

mega_sweeps = []
for pnts in points:
    mega_sweeps.append(usf.Sweep.combine_sweeps([swp for swp in sweeps if swp.points==pnts]))
lm,hm = mega_sweeps
import pandas as pd


# Create a DataFrame with the specified columns
data = {
    'date'     : [int(x) for x in lm.date],
    'time'     : [float(x) for x in lm.daytime],
    'latitude' : [float(x[1]) for x in lm.location],
    'longitude': [float(x[0]) for x in lm.location],
    'elevation': [float(x[2]) for x in lm.location],
    'system_id': [0 for _ in lm.date],
}

df = pd.DataFrame(data)
df = df.sort_values(by='time')

import plotly.graph_objects as go

fig = go.Figure()



# Combined data
fig.add_trace(go.Scatter(x=hm.time.mean(0), y=hm.data.mean(0), mode='lines+markers', name='High Mass Mean Combined', showlegend=False))
fig.add_trace(go.Scatter(x=lm.time.mean(0), y=lm.data.mean(0), mode='lines+markers', name='Low Mass Mean Combined', showlegend=False))

fig.update_layout(
    xaxis_type="log",
    yaxis_type="log",
    xaxis_title="time [s]",
    yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
    margin=dict(t=30)
)



lats = df['latitude'].values
lons = df['longitude'].values

ge_url = "http://www.google.cn/maps/vt?lyrs=s@189&gl=cn&x={x}&y={y}&z={z}"


import plotly.express as px

map = px.scatter_map(df, lat="latitude", lon="longitude", zoom=14)
map.update_layout(    map_style="white-bg",
    map_layers=[
        {
            "below": 'traces',
            "sourcetype": "raster",
            "sourceattribution": "Google Earth",
            "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
        }])
map.update_layout(margin={"r":0,"t":0,"l":0,"b":0})


from plogly import Log, Borehole, Section

logrho = np.array([20, 80, 40])

logrho = np.array([20, 80, 40])
lg = Log(logrho, [0, 10-1, 20-1], [10-1, 20-1, 80], '')
mod_fig = lg.plot(cmap='turbo', x_offset=-1, zmin=0, zmax=100)

for i in range(len(df)):
    lg = Log(logrho, [0, 10+i, 20+i], [10+i, 20+i, 80], '')
    lg.plot(cmap='turbo', x_offset=i, fig=mod_fig,  zmin=0, zmax=100, cbar=False)

from dash import Dash, dash_table

table_overview = dash_table.DataTable(df.to_dict('records'), [{"name": i, "id": i} for i in df.columns], id='table-overview')


