import dash
import dash_mantine_components as dmc
from dash import Dash, html, Output, Input, State
from dash.exceptions import PreventUpdate

import dash_flexlayout as dfl

app = dash.Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets')

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
                    {
                        "type":"tab",
                        "name": "Two",
                        "component": "text",
                        "id": "tab-panels",
                        "tabEnableClose": False,
                    }]},
    ],
    "layout": {
        "type": "row",
        "weight": 100,
        "children": [
            {
                "type": "tabset",
                "weight": 50,
                "selected": 0,
                "children": [
                    {
                        "type": "tab",
                        "name": "Three",
                        "component": "text",
                        "enableFloat": True,
                        "id": "tab-map",
                    }
                ],
            },
            {
                "type": "tabset",
                "weight": 50,
                "selected": 0,
                "children": [
                    {
                        "type": "tab",
                        "name": "Four",
                        "component": "text",
                        "id": "tab-data",
                    },
                    {
                        "type": "tab",
                        "name": "ttem",
                        "component": "text",
                        "id": "tab-ttem",
                    },                    
                    {
                        "type": "tab",
                        "name": "Five",
                        "component": "text",
                        "id": "tab-table",
                    },
                    {
                        "type": "tab",
                        "name": "Six",
                        "component": "text",
                        "id": "tab-model",
                    },
                ],
            },
        ],
    },
}

import example_panels as ep
import plotly.graph_objects as go
import json

from dash import dcc
nodes = [
    dfl.Tab(id="tab-map", children=[dcc.Graph(figure = ep.map, style={'height': '100%'}, id='map'),]),
    dfl.Tab(id="tab-table", children=[ep.table_overview]),
    dfl.Tab(id="tab-data", children=[dcc.Graph(figure=ep.fig, mathjax=True, id='dbdt')]),
    dfl.Tab(id='tab-ttem', children=[dcc.Graph(figure=ep.fig_tTEM, mathjax=True, id='ttem')]),
    dfl.Tab(id="tab-model", children=[dcc.Graph(figure=ep.mod_fig, mathjax=True, style={'height': '100%', 'width': '100%'})]),
    dfl.Tab(
        id="side-1",
        children=[
            html.Button("Get Layout JSON", id="get-layout-button", style={'margin': '10px'}),
            html.Pre(id="layout-json-output", style={'whiteSpace': 'pre-wrap', 'border': '1px solid #ccc', 'padding': '10px'}),
        ],
    ),
    dfl.Tab(id="tab-panels", children=[ep.panel_list])
]

headers = {
    "tab-map": "Map",  # Use plain strings instead of dmc.Title
    "tab-table": "Site Table",
    "tab-data": "Data",
    "tab-ttem": "tTEM",
    "tab-model": "Model",
    "side-1": "Side Tab",
    "tab-panels": "Panels",
}


app.layout = dfl.FlexLayout(
    id="flex-layout",
    model=config,
    children=nodes,
    useStateForModel=True,
    headers=headers,
)


# @app.callback(
#     Output("button-3-output", "children"),
#     [
#         Input("button-3", "n_clicks"),
#     ],
# )
# def update_button_3_output(n_clicks):
#     return f"Clicked {n_clicks} times!"


# @app.callback(Output("layout-model", "children"), [Input("flex-layout", "model")])
# def show_model_layout(layout):
#     return str(layout)


@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Output('dbdt', 'figure', allow_duplicate=True),
    State('map', 'figure'),
    State('dbdt', 'figure'),
    Input('table-overview', 'selected_cells'),
    prevent_initial_call=True,
)
def update_map(epmap, dbdt, selected_cells):
    if not selected_cells:
        raise PreventUpdate
    row_ids = [cell['row'] for cell in selected_cells]
    epmap['data'][0]['selectedpoints'] = row_ids
    
    fig = go.Figure()

    hm_time = ep.hm.time.mean(0)
    lm_time = ep.lm.time.mean(0)
    # Combined data
    for i_row in row_ids:
        fig.add_trace(go.Scatter(x=hm_time, y=ep.hm.data[i_row], mode='lines+markers', showlegend=False, line_color="#2D81FF"))
        fig.add_trace(go.Scatter(x=lm_time, y=ep.lm.data[i_row], mode='lines+markers', showlegend=False, line_color="#FF2727"))

    fig.update_layout(
        xaxis_type="log",
        yaxis_type="log",
        xaxis_title="time [s]",
        yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
        margin=dict(t=30)
    )
    
    return epmap, fig.to_dict()

@app.callback(
    Output('dbdt', 'figure', allow_duplicate=True),
    State('dbdt', 'figure'),
    Input('map', 'selectedData'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def update_dbdt(dbdt, selected_data):
    if not selected_data or 'points' not in selected_data:
        raise PreventUpdate

    # Extract selected points
    selected_points = [point['pointIndex'] for point in selected_data['points']]

    fig = go.Figure()

    hm_time = ep.hm.time.mean(0)
    lm_time = ep.lm.time.mean(0)

    # Update dbdt curves based on selected points
    for i_point in selected_points:
        fig.add_trace(go.Scatter(x=hm_time, y=ep.hm.data[i_point], mode='lines+markers', showlegend=False, line_color="#2D81FF"))
        fig.add_trace(go.Scatter(x=lm_time, y=ep.lm.data[i_point], mode='lines+markers', showlegend=False, line_color="#FF2727"))

    fig.update_layout(
        xaxis_type="log",
        yaxis_type="log",
        xaxis_title="time [s]",
        yaxis_title="$\\frac{dB}{dt}$ \\[V / m$^2$\\]",
        margin=dict(t=30)
    )

    return fig

@app.callback(
    Output('map', 'figure'),
    Input('map', 'clickData'),
    State('map', 'figure'),
    prevent_initial_call=True
)
def draw_lines_on_map(click_data, current_figure):
    if not click_data or 'points' not in click_data:
        raise PreventUpdate

    # Extract clicked point coordinates
    clicked_point = click_data['points'][0]
    lat = clicked_point['lat']
    lon = clicked_point['lon']

    # Initialize or update the line data
    if 'line_data' not in current_figure:
        current_figure['line_data'] = {'lat': [], 'lon': []}

    current_figure['line_data']['lat'].append(lat)
    current_figure['line_data']['lon'].append(lon)

    # Add the line to the map
    current_figure['data'].append({
        'type': 'scattermapbox',
        'lat': current_figure['line_data']['lat'],
        'lon': current_figure['line_data']['lon'],
        'mode': 'lines+markers',
        'line': {'color': 'blue', 'width': 2},
        'marker': {'size': 8, 'color': 'red'}
    })

    return current_figure

@app.callback(
    Output('container-button-basic', 'children'),
    Input('submit-val', 'n_clicks'),
    State('input-on-submit', 'value'),
    prevent_initial_call=True
)
def update_output(n_clicks, value):
    return 'The input value was "{}" and the button has been clicked {} times'.format(
        value,
        n_clicks
    )

# Callback to update the layout JSON
@app.callback(
    Output("layout-json-output", "children"),
    Input("get-layout-button", "n_clicks"),
    prevent_initial_call=True
)
def get_layout_json(n_clicks):
    # Return the current layout (config) as JSON
    return json.dumps(config, indent=4)




app.title = 'sea-anemone'


if __name__ == "__main__":
    app.run(debug=True, port=8050, dev_tools_hot_reload=True, dev_tools_ui=True)