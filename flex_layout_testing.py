from dash import Dash, html
from dash_flexlayout import FlexLayout, FlexRow, FlexColumn

app = Dash(__name__)

app.layout = html.Div(
    children=[
        html.H1("Embedding FlexLayout in html.Div"),
        FlexLayout(
            children=[
                FlexRow(
                    children=[
                        FlexColumn(html.Div("Column 1", style={"background-color": "lightblue", "padding": "10px"})),
                        FlexColumn(html.Div("Column 2", style={"background-color": "lightgreen", "padding": "10px"})),
                        FlexColumn(html.Div("Column 3", style={"background-color": "lightcoral", "padding": "10px"})),
                    ],
                    style={"margin": "10px"},
                )
            ],
            style={"border": "2px solid black", "padding": "10px"},
        ),
    ],
    style={"padding": "20px"},
)

if __name__ == "__main__":
    app.run_server(debug=True)