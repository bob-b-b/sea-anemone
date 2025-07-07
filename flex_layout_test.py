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
                    },
                    {
                        "type":"tab",
                        "name": "Two1",
                        "component": "text",
                        "id": "tab-dump",
                        "tabEnableClose": False,
                    }
                    
                    ]},
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
                    },
                    {
                        "type": "tab",
                        "name": "Three1",
                        "component": "text",
                        "enableFloat": True,
                        "id": "tab-map_settings",
                    },

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

import map
m1 = map.MapPanel(id='map', data=ep.df, settings_schema=map.settings_schema)

nodes = [
    dfl.Tab(id="tab-map", children=[map.create(ep.df)]),
    dfl.Tab(id='tab-map_settings', children=[m1.render_settings()]),
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
    dfl.Tab(id="tab-panels", children=[ep.panel_list]),
    dfl.Tab(id='tab-dump', children=[
        html.Div('dumping zone')])
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


app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    dfl.FlexLayout(
    id="flex-layout",
    model=config,
    children=nodes,
    useStateForModel=False,
    headers=headers,
)]
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
    prevent_initial_call="initial_duplicate",
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
    prevent_initial_call="initial_duplicate",
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
    font_dict=dict(family='Arial',
               size=12,
               color='black'
               )    
    fig.update_layout(font=font_dict,  # font formatting
                    plot_bgcolor='white',  # background color
                    margin=dict(r=20,t=30,b=10)  # remove white space 
                    )
    # x and y-axis formatting
    fig.update_yaxes(title_text='Y-axis',  # axis label
                    showline=True,  # add line at x=0
                    linecolor='black',  # line color
                    linewidth=2.4, # line size
                    ticks='outside',  # ticks outside axis
                    tickfont=font_dict, # tick label font
                    mirror='allticks',  # add ticks to top/right axes
                    tickwidth=2.4,  # tick width
                    tickcolor='black',  # tick color
                    )
    fig.update_xaxes(title_text='X-axis',
                    showline=True,
                    showticklabels=True,
                    linecolor='black',
                    linewidth=2.4,
                    ticks='outside',
                    tickfont=font_dict,
                    mirror='allticks',
                    tickwidth=2.4,
                    tickcolor='black',
                    )

    return fig

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Input('map', 'clickData'),
    State('map', 'figure'),
    prevent_initial_call="initial_duplicate"
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
    prevent_initial_call='initial_duplicate'
)
def update_output(n_clicks, value):
    return 'The input value was "{}" and the button has been clicked {} times'.format(
        value,
        n_clicks
    )

# Callback to update the layout JSON
@app.callback(
    Output("layout-json-output", "children"),
    [Input("get-layout-button", "n_clicks"),
    Input("flex-layout", "model")],
    prevent_initial_call='initial_duplicate'
)
def get_layout_json(n_clicks, layout):
    # Return the current layout (config) as JSON
    return json.dumps(layout, indent=4)


app.title = 'sea-anemone'

location = dcc.Location('url')

# Need all dependant components here to prevent an infinite callback loop
@app.callback(
    Output('tab-dump', 'children'),
    Output('url', 'href'),
    [Input('url', 'href')],
    prevent_initial_call='initial_duplicate'
)
def handle_navigation(fragment):
    print('fragment: ', str(fragment))
    return html.Div(fragment), fragment.split('#')[0] if '#' in fragment else fragment

from dash.dependencies import Input, Output, State, ALL

# Suppose your panel instance is called `panel`
# @app.callback(
#     Output(m1.id, 'figure', allow_duplicate=True),
#     [Input({'type': f'settings-{m1.id}', 'key': ALL}, 'value')],
#     [State(m1.id, 'figure')],
#     prevent_initial_call='initial_duplicate'    
# )
# def update_map_panel(settings_values, current_figure):
#     # Map settings_values to keys from the schema
#     keys = list(m1.settings_schema['properties'].keys())
#     new_settings = dict(zip(keys, settings_values))
#     m1.settings = new_settings
#     # Re-render the map with new settings
#     fig = m1.render().figure
#     return fig


import os
if __name__ == "__main__":
    # os.system('start chrome --app=\"http://127.0.0.1:8050/\"')
    app.run(debug=True, port=8050, dev_tools_hot_reload=True, dev_tools_ui=True)
    
    # start chrome --app="http://127.0.0.1:8050/"
