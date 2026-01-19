import sys, os

fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)
from panels import *

from dash import dcc
from dash import Dash, callback_context
from dash.exceptions import PreventUpdate
from dash_bootstrap_components import Button, ButtonGroup, themes
import dash_bootstrap_components as dbc
import tempfile, shutil, zipfile

from temframe import TEMframe

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "sea anemone"



import os

global TABLES

df_data = None
df_mods = None
df_overview = None

import pandas as pd
# df_overview = pd.DataFrame(columns=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'])



if os.path.exists('anemone_backup'):
    session_files = [f for f in os.listdir('anemone_backup') if f.endswith('.zip')]
    print(session_files)
else:
    os.mkdir('anemone_backup')
    session_files = None



TABLES = {
    'data': df_data,
    'overview': df_overview,
    'models': df_mods
}




m1    = Map(data=df_overview)
dbdt1 = dbdtSounding(dataframe=df_data)
dbdt2 = dbdtSection(dataframe=df_data)
u1    = Upload(session_files=session_files)
# t1    = Table(df_overview, id='table_overview', settings=TableSettings('table_overview', visible_columns=[True]*len(df_overview.columns)))


mod1 = ModelGraph(   dataframe=df_mods )
mod2 = ModelSection( dataframe=df_mods )


x = html.Div([
      dcc.Markdown(children='### buttons and hot keys'),
      html.Div(
          [
            dbc.ButtonGroup([
              dbc.Button("disable [ctrl+d]", id='disableButton'),
              dbc.Button("enable  [ctrl+e]", id='enableButton'),
            ]),
            dbc.ButtonGroup([
              dbc.Button("previous [<-]", id='highlight_prev'),
              dbc.Button("next [->]", id='highlight_next'),
            ]),
            dbc.ButtonGroup([
                dbc.Button("save [ctrl+s]", id='saveButton'),
                dbc.Button("save as [ctrl+shift+s]", id='saveAsButton'),
                dbc.Button("open [ctrl+o]", id='openButton'),
            ])
          ], style={'padding': '10px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}
      ),
      dcc.Location(id='url_button'),
      ]
, id='processing_buttons')


stmod = StartingModel.standard(rho=10.)

panels = [u1, m1, dbdt1, dbdt2, mod1, mod2, stmod]
nodes = [node for panel in panels for node in panel.to_nodes()]+[dfl.Tab(id=f'tab-processing_buttons', children=[x]), dfl.Tab(id='tab-panel_list', children=[panel_list])]


html_header = html.H1('Sea Anemone', style={'width': '100%'})

import layouts

app.layout = html.Div([
    dcc.Location(id='url', refresh='callback-nav'),
    html.Div([
        dbc.ButtonGroup([
            dbc.Button("1. Load Data", id="upload_layout",    color="primary"),
            dbc.Button("2. Process",   id="process_layout", disabled=True, color="secondary"),
            dbc.Button("3. Invert",    id="invert_layout",  disabled=True, color="secondary"),
            dbc.Button("4. Review",    id="review_layout",  disabled=True, color="secondary"),
        ], style={'width': '100%'})
    ], style={
        'position': 'fixed',
        'top': '0',
        'left': '0',
        'right': '0',
        'height': '60px',
        'width': '100%',
        'background': '#f8f9fa',
        'borderBottom': '1px solid #ddd',
        'zIndex': '1000',
        'display': 'flex',
        'alignItems': 'center',
        # 'justifyContent': 'space-between',
        'padding': '0 10px'
    }),
    html.Div([
        dfl.FlexLayout(
            id="flex-layout",
            model=layouts.upload,
            children=nodes,
            useStateForModel=False,        
        ),
    ], style={'marginTop': '60px'}),  # Push content below fixed header
    html.Div(id='output-click')
])

for panel in panels:
    panel.add_callbacks(app)

@app.callback(
    [ 
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM',     'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
    ],
    [Input('map', 'relayoutData'), Input('map', 'selectedData')],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def handle_map_interactions(relayout_data, selected_data):
    """Handle both drawing and selection on the map"""
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    trigger_prop = ctx.triggered[0]['prop_id'].split('.')[1]
    
    selected_sites = []
    
    # Handle drawing interactions
    if trigger_prop == 'relayoutData' and relayout_data:
        # Check if shapes were drawn
        if 'shapes' in relayout_data:
            m1.drawn_shapes = relayout_data['shapes']
            selected_sites = m1.get_selected_sites()
        # Handle shape deletion
        elif any(key.startswith('shapes[') and key.endswith('].x0') for key in relayout_data.keys()):
            # Update shapes if they were modified
            shapes = []
            i = 0
            while f'shapes[{i}].x0' in relayout_data:
                shape = {
                    'type': relayout_data.get(f'shapes[{i}].type', 'rect'),
                    'x0': relayout_data.get(f'shapes[{i}].x0'),
                    'x1': relayout_data.get(f'shapes[{i}].x1'),
                    'y0': relayout_data.get(f'shapes[{i}].y0'),
                    'y1': relayout_data.get(f'shapes[{i}].y1'),
                }
                shapes.append(shape)
                i += 1
            m1.drawn_shapes = shapes
            selected_sites = m1.get_selected_sites()
    
    # Handle point selection
    elif trigger_prop == 'selectedData' and selected_data and 'points' in selected_data:
        selected_sites = [point['pointIndex'] for point in selected_data['points']]+[-1]
    
    # If no sites selected, don't update
    if not selected_sites:
        raise PreventUpdate

    df_data = TABLES['data']

    # Update dataframes with selected sites
    new_df = df_data[df_data['site_id'].isin(selected_sites)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df

    df_mods = TABLES['models']
    if df_mods is not None:
        new_mod = df_mods[df_mods['site_id'].isin(selected_sites)]
        mod1.highlighted = None
        mod1.dataframe = new_mod 
        mod2.dataframe = new_mod

    
    return dbdt1.render(), dbdt2.render(), mod1.render(), mod2.render()


from dash import Input, Output, State, html, dcc, ctx

app.clientside_callback(
    """
        function(id) {
            document.addEventListener("keydown", function(event) {
                // Check if focus is on an input element
                const activeElement = document.activeElement;
                const isInputFocused = activeElement && (
                    activeElement.tagName === 'INPUT' || 
                    activeElement.tagName === 'TEXTAREA' || 
                    activeElement.contentEditable === 'true'
                );
                
                if (event.ctrlKey) {
                    if (event.key == 'd') {
                        document.getElementById('disableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'e') {
                        document.getElementById('enableButton').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 's') {
                        if (event.shiftKey) {
                            document.getElementById('saveAsButton').click()
                        } else {
                            document.getElementById('saveButton').click()
                        }
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }
                
                // Arrow keys without Ctrl, but only if not typing in an input
                if (!isInputFocused) {
                    if (event.key == 'left') {
                        document.getElementById('highlight_prev').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'right') {
                        document.getElementById('highlight_next').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                }
            });
            return window.dash_clientside.no_update       
        }
    """,
    Output("disableButton", "id"),
    Input("disableButton", "id")
)


@app.callback(
    [
        Output("output-click", "children"),
        Output("tTEM", "figure", allow_duplicate=True), Output("sounding", "figure", allow_duplicate=True)
     ],
    Input("disableButton", "n_clicks"),
    Input("enableButton", "n_clicks"),
    State("tTEM", "selectedData"),
    State("sounding", "selectedData"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def show_value(n1, n2, ttem_selected, sounding_selected):
    if str(ctx.triggered_id) == 'disableButton':
        inuse = False
    elif str(ctx.triggered_id) == 'enableButton':
        inuse = True

    if ttem_selected:
        data_ids = [point['customdata'][1] for point in ttem_selected['points'] if 'customdata' in point]
    elif sounding_selected:
        data_ids = [point['customdata'][1] for point in sounding_selected['points'] if 'customdata' in point]
    else:
        raise PreventUpdate
    df_data = TABLES['data']
    
    df_data.loc[df_data['data_id'].isin(data_ids), 'inuse_manual'] = inuse
    df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'])
    dbdt1.dataframe = df_data[df_data['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_data[df_data['site_id'].isin(dbdt2.dataframe['site_id'].unique())]
    return ctx.triggered_id, dbdt2.render(), dbdt1.render()

@app.callback(
    Output('output-click', 'children', allow_duplicate=True),
    Input('saveButton', 'n_clicks'),
    Input('saveAsButton', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def save_session(n1, n2):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    import datetime
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    if trigger_id == 'saveButton':
        print('triggered saveButton')
    elif trigger_id == 'saveAsButton':
        print('triggered saveAsButton')
    else:
        raise PreventUpdate

    # tmpdir = tempfile.mkdtemp(prefix='anemone_backup_')
    # try:
    #     # Save data (assumes TEMframe.save(directory) writes backup files into directory)
    #     if TABLES['data'] is not None:
    #         TABLES['data'].save(tmpdir)

    #     # Save models.csv if present
    #     if TABLES['models'] is not None:
    #         TABLES['models'].to_csv(os.path.join(tmpdir, 'models.csv'), index=False)

    #     # Create zip archive next to this script
    #     zip_path = os.path.join('anemone_backup', fname)
    #     with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    #         for root, _, files in os.walk(tmpdir):
    #             print(files)
    #             for f in files:
    #                 full = os.path.join(root, f)
    #                 arcname = os.path.relpath(full, tmpdir)
    #                 zf.write(full, arcname)

    #     print(f'data saved to {zip_path}')
    # finally:
    #     shutil.rmtree(tmpdir)

    return f'Session saved as {fname}'

@app.callback(
    [
        Output("output-click", "children", allow_duplicate=True),
        Output('map', 'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('starting_model', 'figure', allow_duplicate=True)
    ],
    Input('highlight_prev', 'n_clicks'),
    Input('highlight_next', 'n_clicks'),
    State('invert_layout',  'color'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def highlight_change(n1, n2, invert_layout_color):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    highlighted = m1.highlighted
    if trigger_id == 'highlight_prev':
        highlight_change = -1
    elif trigger_id == 'highlight_next':
        highlight_change = 1

    if highlighted is None:
        highlighted = 0
    else:
        highlighted += highlight_change
    df_data = TABLES['data']
    m1.highlighted = highlighted
    mod1.highlighted = highlighted
    dbdt1.dataframe = df_data[df_data['site_id'] == highlighted]
    print('invert layout color:', invert_layout_color)
    if invert_layout_color == 'primary':
        print('will launch an inversion next time')
    

    return ctx.triggered_id, m1.render(), mod1.render(), dbdt1.render(), stmod.render()

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    [
        Input('model_section', 'hoverData'),
        Input('tTEM', 'hoverData'),
    ],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def cross_panel_hover(sounding_hover, ttem_hover):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    hover_data = ctx.triggered[0]['value']
    if not hover_data or 'points' not in hover_data:
        raise PreventUpdate
    if trigger_id == 'tTEM':
        x_value = hover_data['points'][0]['x']
        site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
        m1.highlighted = site_id
    elif trigger_id == 'model_section':
        x_value = hover_data['points'][0]['x']
        site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
        m1.highlighted = site_id

    return m1.render()

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Output('model_graph', 'figure', allow_duplicate=True),
    Output('sounding', 'figure', allow_duplicate=True),
    Output('starting_model', 'figure', allow_duplicate=True),
    [
        Input('model_section', 'clickData'),
        Input('tTEM', 'clickData'),
        Input('map', 'clickData'),
        State('invert_layout',  'color'),
    ],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def cross_panel_click(model_click, ttem_click, map_click, invert_layout_color):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    click_data = ctx.triggered[0]['value']
    if not click_data or 'points' not in click_data:
        raise PreventUpdate
    if trigger_id == 'tTEM':
        x_value = click_data['points'][0]['x']
        site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'model_section':
        x_value = click_data['points'][0]['x']
        site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'map':
        site_id = int(click_data['points'][0]['pointNumber'])
    else:
        site_id = None
    df_data = TABLES['data']
    m1.highlighted = site_id
    mod1.highlighted = site_id
    dbdt1.dataframe = df_data[df_data['site_id'] == site_id]
    if invert_layout_color == 'primary':
        df_layers, df_site, _ = df_data.invert_site(site_id)
        # if mod1.dataframe is not None:
        #     df_layers = pd.concat([mod1.dataframe[df_data['site_id'] != site_id], df_layers], ignore_index=True)
        mod1.dataframe = df_layers
        dbdt1.dataframe = df_site
    return m1.render(), mod1.render(), dbdt1.render(), mod1.render()



@app.callback(
    [
        Output('starting_model', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('review_layout', 'n_clicks', allow_duplicate=True),
        Output('review_layout', 'disabled', allow_duplicate=True)
    ],
    Input('invert_all_button', 'n_clicks'),
    State('review_layout', 'n_clicks'),  # Add this state to get current value

    prevent_initial_call=True
)
def launch_inversion(n_clicks, current_review_clicks):
    if n_clicks:
        from torch import from_numpy
        rho = from_numpy(stmod.dataframe['resistivity'].values)
        z   = from_numpy(stmod.dataframe['depth'].values[:-1])

        res_start                        = LogResistivity.smooth(rho,z) 
        TABLES['models'], TABLES['data'] = TABLES['data'].invert(res_start)
        mod1.dataframe                   = TABLES['models'].copy()
        mod2.dataframe                   = TABLES['models'].copy()
        dbdt1.dataframe                  = TABLES['data'].copy()
        dbdt2.dataframe                  = TABLES['data'].copy()
        new_review_clicks = (current_review_clicks or 0) + 1
        return stmod.render(), mod2.render(), dbdt1.render(), new_review_clicks, False
    raise PreventUpdate

@app.callback(
    [Output('output-data-upload', 'children'),
     Output('map', 'figure', allow_duplicate=True),
     Output('sounding', 'figure', allow_duplicate=True),
     Output('tTEM', 'figure', allow_duplicate=True),
     Output('process_layout', 'disabled', allow_duplicate=True),
     Output('invert_layout', 'disabled', allow_duplicate=True),
     Output('process_layout', 'n_clicks', allow_duplicate=True),
    #  Output(t1.id, 'children', allow_duplicate=True),
    ],
    Input('upload-data', 'contents'),
    State('process_layout', 'n_clicks'),
    prevent_initial_call=True
)
def upload_file(contents, current_process_clicks):
    if contents is None:
        raise PreventUpdate
    
    TABLES['data']            = TEMframe.from_zip_content(contents[0])
    TABLES['data'].history    = ['df_data = TEMframe.from_zip_content("uploaded_data_zip.txt")']
    TABLES['data']['include'] = TABLES['data']['inuse_manual'].astype(bool, copy=False).fillna(TABLES['data']['inuse_auto'])
    TABLES['overview']        = TABLES['data'].overview()
    TABLES['models']          = None

    dbdt1.dataframe = TABLES['data'].copy()
    dbdt2.dataframe = TABLES['data'].copy()
    m1.dataframe    = TABLES['overview']
    mod1.dataframe  = TABLES['models']
    mod2.dataframe  = TABLES['models']
    # t1.dataframe = TABLES['overview'].copy()
    new_process_clicks = (current_process_clicks or 0) + 1

    return html.Div("File uploaded successfully."), m1.render(), dbdt1.render(), dbdt2.render(), False, False, new_process_clicks#, t1.render()

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Input('flex-layout', 'model'),
    prevent_initial_call=True

)
def print_flex_layout_model(model):
    print(f"Flex layout model: {model}")
    return m1.render()

@app.callback(
    [
        Output('flex-layout', 'model'),
        Output('upload_layout', 'color'),
        Output('process_layout', 'color'),
        Output('invert_layout', 'color'),
        Output('review_layout', 'color'),
    ],
    [
        State('flex-layout', 'model'),
        Input("upload_layout", 'n_clicks'),
        Input("process_layout", 'n_clicks'),
        Input("invert_layout", 'n_clicks'),
        Input("review_layout", 'n_clicks'),
    ],
    prevent_initial_call=True
)
def update_layout(model, load_clicks, process_clicks, invert_clicks, review_clicks):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    # Get the ID of the button that was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == "upload_layout":
        return layouts.upload, 'primary', 'secondary', 'secondary', 'secondary'
    elif button_id == "process_layout":
        return layouts.data, 'secondary', 'primary', 'secondary', 'secondary'
    elif button_id == "invert_layout":
        return layouts.invert, 'secondary', 'secondary', 'primary', 'secondary'
    elif button_id == "review_layout":
        return layouts.review, 'secondary', 'secondary', 'secondary', 'primary'
    return model, 'secondary', 'secondary', 'secondary', 'secondary'

@app.callback(
    [
        Output('flex-layout',    'model', allow_duplicate=True),

        Output('upload_layout',  'color',  allow_duplicate=True),
        Output('process_layout', 'color', allow_duplicate=True),
        Output('invert_layout',  'color', allow_duplicate=True),
        Output('review_layout',  'color', allow_duplicate=True), #Output('review_layout', 'disabled', allow_duplicate=True)

        Output('upload_layout',  'disabled',  allow_duplicate=True),
        Output('process_layout', 'disabled', allow_duplicate=True),
        Output('invert_layout',  'disabled', allow_duplicate=True),
        Output('review_layout',  'disabled', allow_duplicate=True), #Output('review_layout', 'disabled', allow_duplicate=True)

        Output('map', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
    ],        
    Input('url', 'hash'),
    State('flex-layout', 'model'),
    prevent_initial_call=True,
    
)
def handle_url_hash(url_hash, model):
    layout=model
    print(f'url hash: {url_hash}')
    if url_hash.startswith('#load'):
        fname = url_hash.split('=')[1]
        tmpTables = TEMframe.from_session(f'anemone_backup/{fname}')
        TABLES['data']            = tmpTables['data']
        TABLES['overview']        = tmpTables['overview']
        TABLES['models']          = tmpTables['models']
        dbdt1.dataframe = TABLES['data'].copy()
        dbdt2.dataframe = TABLES['data'].copy()
        m1.dataframe    = TABLES['overview'].copy()
        mod1.dataframe  = TABLES['models'].copy()
        mod2.dataframe  = TABLES['models'].copy()
        figures = [m1.render(), dbdt1.render(), dbdt2.render(), mod2.render()]

        if TABLES['models'] is not None:
            res_list  = [layouts.review]
            res_list += ['secondary', 'secondary', 'secondary', 'primary']
            res_list += [False, False, False, False]
            res_list += figures
        else:
            res_list  = [layouts.data]
            res_list += ['secondary', 'primary', 'secondary', 'secondary']
            res_list += [False, False, False, True]
            res_list += figures
        return res_list
    else:
        print('no valid hash found')
        raise PreventUpdate


import signal
@app.server.route("/shutdown", methods=["POST"])
def shutdown():
    os.kill(os.getpid(), signal.SIGINT)  # Send a signal to the process to terminate


try:
    app.run(port=8050, debug=True)
except Exception as e:
    print(f"Error running app: {e}")
# finally:
#     print('closing app, saving data to zip...')
#     tmpdir = tempfile.mkdtemp(prefix='anemone_backup_')
#     try:
#         # Save data (assumes TEMframe.save(directory) writes backup files into directory)
#         if TABLES['data'] is not None:
#             TABLES['data'].save(tmpdir)

#         # Save models.csv if present
#         if TABLES['models'] is not None:
#             TABLES['models'].to_csv(os.path.join(tmpdir, 'models.csv'), index=False)

#         # Create zip archive next to this script
#         zip_path = os.path.join('anemone_backup', 'session1.zip')
#         with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
#             for root, _, files in os.walk(tmpdir):
#                 print(files)
#                 for f in files:
#                     full = os.path.join(root, f)
#                     arcname = os.path.relpath(full, tmpdir)
#                     zf.write(full, arcname)

#         print(f'data saved to {zip_path}')
#     finally:
#         shutil.rmtree(tmpdir)

#start msedge --app=http://127.0.0.1:8050/