import dash
from dash import html, dcc, Input, Output, State
import sys
import io
import traceback
import numpy as np

# Create the Dash app
app = dash.Dash(__name__)
app.title = "Python Interpreter in Dash"

# Layout
app.layout = html.Div([
    html.H2("Python Interpreter"),
    dcc.Textarea(
        id='code-input',
        placeholder='Type Python code here...',
        style={'width': '100%', 'height': 200}
    ),
    html.Br(),
    html.Button('Run Code', id='run-btn', n_clicks=0),
    html.H4("Output:"),
    html.Pre(id='code-output', style={'backgroundColor': '#f4f4f4', 'padding': '10px'})
])

# Callback to execute Python code
@app.callback(
    Output('code-output', 'children'),
    Input('run-btn', 'n_clicks'),
    State('code-input', 'value')
)
def run_python_code(n_clicks, code):
    if not code:
        return "No code entered."

    # Redirect stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    redirected_output = sys.stdout = io.StringIO()
    redirected_error = sys.stderr = io.StringIO()

    try:
        # Execute the code in a restricted namespace
        exec(code)#, {"__builtins__": __builtins__}, {})
        output = redirected_output.getvalue()
        errors = redirected_error.getvalue()
        return output + errors if output or errors else "Code executed successfully (no output)."
    except Exception:
        return traceback.format_exc()
    finally:
        # Restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr

# Run the app
if __name__ == '__main__':
    app.run(debug=True)