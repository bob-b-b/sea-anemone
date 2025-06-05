import dash
from dash import html
from dash_mosaic import DashMosaic
from dash import Dash, dcc, html
import dash_bootstrap_components as dbc
from dash import Dash, html, Output, Input, State
from dash.exceptions import PreventUpdate

app = dash.Dash(__name__, prevent_initial_callbacks=True)

import plotly.io as pio
import plotly.express as px

import plotly.graph_objects as go
pio.templates["draft"] = go.layout.Template(layout=go.Layout(title_font=dict(size=1)))
pio.templates.default = "plotly+draft"

import example_panels as ep



initial_layout = {
    'direction': 'row',
    'first': {'direction': 'column', 'first': 1, 'second': 4},
    'second': {
        'direction': 'column',
        'first': 2,
        'second': 3,
    },
    'splitPercentage': 40,
}

tile_content = {
    1: dcc.Graph(figure = ep.map, style={'height': '100vh'}, id='map'),
    2: dcc.Graph(figure=ep.fig,
        mathjax=True,
        style={'height': '100%', 'width': '100%'},
    id='dbdt'),
    3: dcc.Graph(figure=ep.mod_fig,
        mathjax=True, style={'height': '100%', 'width': '100%'}),
    4: html.Div([ep.table_overview], style={'overflow-y': 'scroll', 'height': '100%'}),
}

window_selection_dropdown = dcc.Dropdown(
    id='window-dropdown',
    options=[
        {'label': 'Map', 'value': 1},
        {'label': 'Data', 'value': 2},
        {'label': 'Model', 'value': 3},
        {'label': 'Overview', 'value': 4}
    ],
    placeholder='Select a window to add',
    style={'width': '300px', 'display': 'inline-block'}
)

layout_mosaic = DashMosaic(
    id='mosaic',
    layout=initial_layout,
    theme='Blueprint',
    tileContent=tile_content,
    windowTitles={1: "Map", 2: "Data", 3: "Model", 4: "Overview"},
    showSplitButton=False,
    showExpandButton=False,
    showRemoveButton=True,
    showNavbar=False,
    style={'height': '90vh', 'width': '100vw'}
)

app.layout = html.Div([
    html.Div([html.H1("sea-anemone", style={'width':'300px', 'display':'inline-block'}), window_selection_dropdown],
      style={'padding': '10px', 'backgroundColor': '#f8f9fa'}),
    layout_mosaic,
    html.Div(id='output', style={'display': 'none'})
])

@app.callback(
    Output('mosaic', 'tileContent'),
    Output('mosaic', 'windowTitles'),
    Output('mosaic', 'layout'),
    Input('window-dropdown', 'value'),
    prevent_initial_call=True
)
def add_window(selected_value):
    if selected_value is None:
        raise PreventUpdate
    layout_mosaic.tileContent[5] = layout_mosaic.tileContent[selected_value]
    layout_mosaic.windowTitles[5] = f"Window {selected_value}"
    layout_mosaic.layout['second']['second'] = 5
    return layout_mosaic.tileContent, layout_mosaic.windowTitles, layout_mosaic.layout




@app.callback(
    Output('map', 'figure'),
    Output('dbdt', 'figure'),
    State('map', 'figure'),
    State('dbdt', 'figure'),
    Input('table-overview', 'selected_cells'),
    prevent_initial_call=True
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
    Output('table-overview', 'selected_cells'),
    Output('dbdt', 'figure'),
    State('dbdt', 'figure'),
    Input('map', 'selectedData'),
)

if __name__ == '__main__':
    app.run(debug=True)