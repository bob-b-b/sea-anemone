import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objs as go
import numpy as np

app = dash.Dash(__name__)

n_traces = 5
n_samples = 100
fig = go.Figure()
for i in range(n_traces):
    x = np.linspace(-1, 1, n_samples)*4
    y = np.random.randn(n_samples)
    fig.add_trace(go.Scatter(
        x=x, y=y,
        mode='lines+markers',
        name=f'Trace {i+1}',
        opacity=0.1
    ))

app.layout = html.Div([
    dcc.Graph(id='my-graph', figure=fig, clear_on_unhover=True)
])

# Custom clientside callback for legend hover highlighting
app.clientside_callback(
    """
    function(relayoutData, figure) {
        // relayoutData contains legendonly info on click, but not on hover.
        // Plotly does not emit a legend hover event to Dash directly.
        // This workaround dims all traces except those visible.
        if (!figure) { return window.dash_clientside.no_update; }
        let newData = figure.data.map(trace => ({...trace, opacity: 0.1}));
        if (relayoutData && relayoutData['legendonly']) {
            // If a trace is isolated, set its opacity to 1
            let idx = figure.data.findIndex(t => t.name === relayoutData['legendonly']);
            if (idx >= 0) newData[idx].opacity = 1.0;
        } else {
            // If nothing is isolated, restore all opacities
            newData = figure.data.map(trace => ({...trace, opacity: 0.1}));
        }
        return {...figure, data: newData};
    }
    """,
    Output('my-graph', 'figure'),
    Input('my-graph', 'relayoutData'),
    State('my-graph', 'figure'),
    prevent_initial_call=True
)

if __name__ == '__main__':
    app.run(debug=True, port=8051)