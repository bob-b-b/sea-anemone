from dash import Dash, dcc, html, Input, Output, dash_table
import plotly.express as px
import pandas as pd
import numpy as np

# Sample data for the table and map
data = {
    'lat': [56.1, 56.2, 56.3],
    'lon': [10.1, 10.2, 10.3],
    'name': ['Point A', 'Point B', 'Point C']
}
df = pd.DataFrame(data)

# Initialize the Dash app
app = Dash(__name__)

# Define the app layout
app.layout = html.Div([
    dash_table.DataTable(
        id='data-table',
        columns=[
            {'name': 'Name', 'id': 'name'},
            {'name': 'Latitude', 'id': 'lat'},
            {'name': 'Longitude', 'id': 'lon'}
        ],
        data=df.to_dict('records'),
        row_selectable='single'
    ),
    dcc.Graph(id='map')
])

# Callback to update the map based on selected row
@app.callback(
    Output('map', 'figure'),
    Input('data-table', 'selected_rows')
)
def update_map(selected_rows):
    if selected_rows is None or len(selected_rows) == 0:
        # Default map with all points
        fig = px.scatter_mapbox(
            df, lat='lat', lon='lon', hover_name='name',
            mapbox_style="carto-positron"
        )
    else:
        # Highlight the selected point
        selected_row = selected_rows[0]
        selected_point = df.iloc[selected_row]
        fig = px.scatter_mapbox(
            df, lat='lat', lon='lon', hover_name='name',
            mapbox_style="carto-positron"
        )
        fig.add_trace(
            px.scatter_mapbox(
                pd.DataFrame([selected_point]), lat='lat', lon='lon',
                mapbox_style="carto-positron"
            ).data[0]
        )
    return fig

if __name__ == '__main__':
    app.run_server(debug=True)
