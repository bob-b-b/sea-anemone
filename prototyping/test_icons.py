import dash
from dash import html
import dash_bootstrap_components as dbc
import dash_mantine_components as dmc

gear = html.Img(id="logo", src="./assets/settings.svg", style={'height':'1cm'})
app = dash.Dash(__name__)

app.layout = html.Div([
    html.Span([
        dbc.Label(gear, style={'cursor': 'pointer'})
    ])
])

if __name__ == '__main__':
    app.run(debug=True)