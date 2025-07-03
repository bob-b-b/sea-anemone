from dash import html, Dash, dcc, Output, Input
from dash_bootstrap_components import Collapse


panel_list_entry_style = {
    'cursor': 'pointer',  # Makes the text clickable
    'padding': '10px',
    'backgroundColor': '#f8f9fa',
    'borderRadius': '5px',
}

app = Dash(__name__)

app.layout = html.Div([
    html.H1('Panels'),
    html.H2('Data', id='header-toggle', style={'cursor': 'pointer'}),
    Collapse(
        html.Div([
            html.Li('Sounding',
                    id='clickable-paragraph1',
                    style=panel_list_entry_style
                ),
            Collapse(
                html.Div([
                    html.Li('section',
                            id='clickable-paragraph2',
                            style=panel_list_entry_style,
                            title="show the data in a tTEM style section"
                        )
                ], style={'paddingLeft': '20px'}),
                id='collapse-level-2'
            )
        ]),
        id='collapse-level-1'
    )
], style={'padding': '10px'})


@app.callback(
    Output('collapse-level-1', 'is_open'),
    Input('header-toggle', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_level_1(n_clicks):
    return True


@app.callback(
    Output('collapse-level-2', 'is_open'),
    Input('clickable-paragraph1', 'n_clicks'),
    prevent_initial_call=True
)
def toggle_level_2(n_clicks):
    return True


if __name__ == '__main__':
    app.run(debug=True)