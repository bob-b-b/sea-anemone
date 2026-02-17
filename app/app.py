import sys, os
from tkinter import filedialog, Tk


fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)

import session
global sesh
sesh = session.Session()

session_tracker = fpath+'/recent_projects.txt'

from panels import *
from inversion_panels import *

from dash import dcc
from dash import Dash#, callback_context
from dash.exceptions import PreventUpdate
from dash import Input, Output, State, html, dcc, ctx
from dash_bootstrap_components import Button, ButtonGroup, themes
import dash_bootstrap_components as dbc
from dash.dash import no_update

from temframe import TEMframe

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "Sea Anemone"


import os



import pandas as pd
# df_overview = pd.DataFrame(columns=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'])




if os.path.exists(session_tracker):
    with open(session_tracker, 'rt') as f:
        session_files = f.readlines()
    session_files = list(set([line.strip() for line in session_files if line.strip() != '']))

else:
    session_files = []


pyInt = PyInterpretter()
m1    = Map(data=sesh.overview)
dbdt1 = dbdtSounding(dataframe=sesh.data)
dbdt2 = dbdtSection(dataframe=sesh.data)
rhoa  = rhoaSounding(dataframe=sesh.data)

u1    = Upload(session_files=session_files)
# t1    = Table(df_overview, id='table_overview', settings=TableSettings('table_overview', visible_columns=[True]*len(df_overview.columns)))
mod1 = ModelGraph(   dataframe=sesh.models )
mod2 = ModelSection( dataframe=sesh.models )
Multi_inv = MultiInversion( dataframe=sesh.data )






#stmod = StartingModel.standard(rho=10.)

# Inv_it = Inversion_iterations.standard(misfit=None,rho=10.)

Sing_inv = Single_site( dataframe=sesh.data, rho=10 )

hkr = HotKeyReminder()

panels = [u1, m1, dbdt1, dbdt2, mod1, mod2, Multi_inv, Sing_inv, pyInt, rhoa, hkr]
nodes = [node for panel in panels for node in panel.to_nodes()]#+[dfl.Tab(id=f'tab-processing_buttons', children=[x])]


html_header = html.H1('Sea Anemone', style={'width': '100%'})

import layouts

flex_layout = dfl.FlexLayout(
            id="flex-layout",
            model=layouts.upload,
            children=nodes,
            useStateForModel=False,        
        )

app.layout = html.Div([
    dcc.Location(id='url', refresh='callback-nav'),
    dcc.Interval(id= "inv-log-poll", interval=1000, n_intervals=0, disabled=True),  # Poll every 2 seconds
    dcc.Store(id="selected-site-id", data=None),
    dcc.Store(id="starting-model", data={"rho": 10.0,"depth": np.cumsum(np.logspace(0, 1.3, 31)).tolist()}),
    dcc.Store(id='starting-model-selected',data=[]),
    html.Div([
        dbc.ButtonGroup([
            dbc.Button("1. Load Data",  id="upload_layout",    color="primary"),
            dbc.Button("2. Process",    id="process_layout",   disabled=True, color="secondary"),
            dbc.Button("3. Invert",     id="invert_layout",    disabled=True, color="secondary"),
            dbc.Button("4. QC",         id="review_layout",    disabled=True, color="secondary"),
            dbc.Button("5. Interpret",  id="interpret_layout", disabled=True, color="secondary"),
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
        'padding': '0 10px'
    }),
    html.Div([flex_layout], style={'marginTop': '60px'}),  # Push content below fixed header
    html.Div(id='output-click')
])

for panel in panels:
    panel.add_callbacks(app)

@app.callback(
    [ 
        dbdt1.output, dbdt2.output, rhoa.output, mod1.output, mod2.output,
    ],
    [Input('map', 'relayoutData'), Input('map', 'selectedData')],
    prevent_initial_call="initial_duplicate",
    allow_duplicate=True
)
def handle_map_interactions(relayout_data, selected_data):
    """Handle both drawing and selection on the map"""
    # ctx = callback_context
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

    df_data = sesh.data

    # Update dataframes with selected sites
    new_df = df_data[df_data['site_id'].isin(selected_sites)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df
    rhoa.dataframe  = new_df

    df_mods = sesh.models
    if df_mods is not None:
        new_mod = df_mods[df_mods['site_id'].isin(selected_sites)]
        mod1.highlighted = None
        mod1.dataframe = new_mod 
        mod2.dataframe = new_mod

    
    return dbdt1.render(), dbdt2.render(), rhoa.render(), mod1.render(), mod2.render()




app.clientside_callback(
    hkr.javascript,
    Output("disableButton", "id"),
    Input("disableButton", "id")
)
@app.callback(
    [
        dbdt1.output, dbdt2.output, rhoa.output,
    ],
    Input("disableButton", "n_clicks"),
    Input("enableButton", "n_clicks"),
    State("tTEM", "selectedData"),
    State("sounding", "selectedData"),
    State("rhoa", "selectedData"),
    prevent_initial_call=True,
    allow_duplicate=True,
)
def show_value(n1, n2, ttem_selected, sounding_selected, rhoa_selected):

    if str(ctx.triggered_id) == 'disableButton':
        inuse = False
    elif str(ctx.triggered_id) == 'enableButton':
        inuse = True


    if ttem_selected and len(ttem_selected['points'])>0:
        data_ids = [point['customdata'][1] for point in ttem_selected['points'] if 'customdata' in point]
    elif sounding_selected and len(sounding_selected['points'])>0:
        data_ids = [point['customdata'][1] for point in sounding_selected['points'] if 'customdata' in point]
    elif rhoa_selected and len(rhoa_selected['points'])>0:
        data_ids = [point['customdata'][1] for point in rhoa_selected['points'] if 'customdata' in point]        
    else:
        raise PreventUpdate
    

    df_data = sesh.data
    
    df_data.loc[df_data['data_id'].isin(data_ids), 'inuse_manual'] = inuse
    df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'])
    dbdt1.dataframe = df_data[df_data['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_data[df_data['site_id'].isin(dbdt2.dataframe['site_id'].unique())]
    rhoa.dataframe  = df_data[df_data['site_id'].isin(rhoa.dataframe['site_id'].unique())]
    return dbdt1.render(), dbdt2.render(), rhoa.render()

@app.callback(
    Output("model_section", "figure", allow_duplicate=True),
    Output("model_graph", "figure", allow_duplicate=True),
    Input("review_layout", "n_clicks"),
    State("invert_layout", "color"),
    prevent_initial_call=True
)
def update_model_on_review(_, invert_color):
    # if invert_color != "primary":
        # raise PreventUpdate
    mod2.dataframe = sesh.models.copy() if sesh.models is not None else None
    mod1.dataframe = sesh.models.copy() if sesh.models is not None else None
    return mod2.render(), mod1.render()

@app.callback(
    Output('output-click', 'children', allow_duplicate=True),
    Input('saveButton', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def save_session(n1):
    if sesh.save_dir is None:
        root = Tk()
        root.withdraw()  # Hide the root window
        folder_path = filedialog.askdirectory(title="Select Save Directory")
        print(folder_path)
        root.destroy()  # Destroy the root window after selection
        if not folder_path:
            raise PreventUpdate
        sesh.save_dir = folder_path + '/' if not folder_path.endswith('/') else folder_path
    if sesh.save_dir not in u1.session_files:
        u1.session_files.append(sesh.save_dir)
        with open(session_tracker, 'w') as f:
            for item in u1.session_files:
                f.write(f"{item}\n")

    sesh.save(folder=sesh.save_dir)
    print(f'Session saved to {sesh.save_dir}')
    return f'Session saved to {sesh.save_dir}'

@app.callback(
    [
        Output("output-click", "children", allow_duplicate=True),
        Output("selected-site-id", "data", allow_duplicate=True),
        Output('map', 'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('multi_inv', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
        Output('tTEM', 'figure', allow_duplicate=True),
    ],
    Input('highlight_prev', 'n_clicks'),
    Input('highlight_next', 'n_clicks'),
    State('invert_layout',  'color'),
    State('flex-layout', 'model'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def highlight_change(n1, n2, invert_layout_color,model):
    # ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    highlighted = m1.highlighted
    if trigger_id == 'highlight_prev':
        highlight_change = -1
    elif trigger_id == 'highlight_next':
        highlight_change = 1

    if highlighted is None:
        PreventUpdate
    else:
        highlighted += highlight_change
    df_data = sesh.data
    m1.highlighted = highlighted
    mod1.highlighted = highlighted
    mod2.highlighted = highlighted
    dbdt2.highlighted = highlighted
    dbdt1.dataframe = df_data[df_data['site_id'] == highlighted]
    print('invert layout color:', invert_layout_color)
    def get_active_tab_id(model):
        if model is None:
            return None

        def search(node):
            if node.get("type") == "tabset":
                return node.get("selected")
            for child in node.get("children", []):
                result = search(child)
                if result:
                    return result
            return None

        return search(model.get("layout", {}))

    active_tab = get_active_tab_id(model)
    # print()
    # if active_tab == 1:
        # Sing_inv.invert_single_site(df_data[df_data['site_id'] == highlighted])
        # print('here?')
    # if invert_layout_color == 'primary':
    #     print('will launch an inversion next time')
        
    
    

    return ctx.triggered_id, highlighted, m1.render(), mod1.render(), dbdt1.render(), Multi_inv.render(), mod2.render(), dbdt2.render()




# @app.callback(
#     Output('map', 'figure', allow_duplicate=True),
#     [
#         Input('model_section', 'hoverData'),
#         Input('tTEM', 'hoverData'),
#     ],
#     prevent_initial_call="initial_duplicate",
#     allow_duplicate=True
# )
# def cross_panel_hover(sounding_hover, ttem_hover):
#     # ctx = callback_context
#     if not ctx.triggered:
#         raise PreventUpdate
#     trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
#     hover_data = ctx.triggered[0]['value']
#     if not hover_data or 'points' not in hover_data:
#         raise PreventUpdate
#     if trigger_id == 'tTEM':
#         x_value = hover_data['points'][0]['x']
#         site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
#         m1.highlighted = site_id
#     elif trigger_id == 'model_section':
#         x_value = hover_data['points'][0]['x']
#         site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
#         m1.highlighted = site_id

#     return m1.render()

@app.callback(
    Output('map', 'figure', allow_duplicate=True),
    Output('model_graph', 'figure', allow_duplicate=True),
    Output('sounding', 'figure', allow_duplicate=True),
    Output('model_section', 'figure', allow_duplicate=True),
    Output('tTEM', 'figure', allow_duplicate=True),
        #Output('table_overview', 'figure', allow_duplicate=True)
    #Output('starting_model', 'figure', allow_duplicate=True),
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
    # ctx = callback_context
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
    df_data = sesh.data
    # Sing_inv.dataframe = df_data[df_data['site_id'] == site_id]
    m1.highlighted = site_id
    mod1.highlighted = site_id
    mod2.highlighted = site_id
    dbdt2.highlighted = site_id
    dbdt1.dataframe = df_data[df_data['site_id'] == site_id]
    # if invert_layout_color == 'primary':
    #     # df_layers, df_site, _ = df_data.invert_site(site_id)
    #     # if mod1.dataframe is not None:
    #     #     df_layers = pd.concat([mod1.dataframe[df_data['site_id'] != site_id], df_layers], ignore_index=True)
    #     mod1.dataframe = df_layers
    #     dbdt1.dataframe = df_site
    return m1.render(), mod1.render(), dbdt1.render(), mod2.render(), dbdt2.render()

# @app.callback(
#     Output("starting-model", "data"),
#     Input("multi_inv", "relayoutData"),
#     Input("inv-single", "relayoutData"),
#     State("starting-model", "data"),
#     prevent_initial_call=True
# )
# def update_starting_model_from_iterations(multi_inv_data, sing_site_data, data):

#     if not ctx.triggered:
#         raise PreventUpdate

#     trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]

#     if trigger_id == "multi_inv":
#         relayoutData = multi_inv_data
#     elif trigger_id == "inv-single":
#         relayoutData = sing_site_data
#     else:
#         raise PreventUpdate

#     if not relayoutData or "shapes[0].x0" not in relayoutData:
#         raise PreventUpdate

#     rho = float(relayoutData["shapes[0].x0"])
#     data["rho"] = rho
#     return data

@app.callback(
    Output("starting-model", "data", allow_duplicate=True),
    Input("multi_inv", "relayoutData"),
    State("starting-model", "data"),
    prevent_initial_call=True
)
def update_starting_model_from_drag(relayout, model):
    if not relayout:
        raise PreventUpdate

    # Look for moved vertical line
    moved = [k for k in relayout if k.endswith(".x0")]
    if not moved:
        raise PreventUpdate

    new_rho = relayout[moved[0]]

    # Update starting model
    model["rho"] = float(new_rho)

    return model

@app.callback(
    Output("starting-model", "data", allow_duplicate=True),
    Input("inv-single", "relayoutData"),
    State("starting-model", "data"),
    prevent_initial_call=True
)
def update_starting_model_from_single_drag(relayout, model):
    if not relayout:
        raise PreventUpdate

    moved = [k for k in relayout if k.endswith(".x0")]
    if not moved:
        raise PreventUpdate

    model["rho"] = float(relayout[moved[0]])
    return model





# @app.callback(
#     Output("starting-model-selected", "data"),
#     Input("multi_inv", "selectedData"),
#     prevent_initial_call=True
# )
# def launch_inversion(n_clicks, current_review_clicks, vc_level,hc_level,starting_model):
#     if n_clicks:
#         from torch import from_numpy, tensor
#         # print('starting model:', starting_model["rho"])
#         rho = tensor(starting_model["rho"]).repeat(len(starting_model["depth"]))
#         z   = tensor(starting_model["depth"][:-1])
        
#         if vc_level == "loose":
#             Vert = 5.0
#         elif vc_level == "medium":
#             Vert = 0.5
#         elif vc_level == "tight":
#             Vert = 0.1

#         if hc_level == "loose":
#             Horz = 5.0
#         elif hc_level == "medium":
#             Horz = 0.6
#         elif hc_level == "tight":
#             Horz = 0.3
#         res_start                        = LogResistivity.smooth(rho,z) 
#         sesh.models, sesh.data = sesh.data.invert(res_start,vc = Vert, hc = Horz)
#         mod1.dataframe                   = sesh.models.copy()
#         mod2.dataframe                   = sesh.models.copy()
#         dbdt1.dataframe                  = sesh.data.copy()
#         dbdt2.dataframe                  = sesh.data.copy()
#         new_review_clicks = (current_review_clicks or 0) + 1
#         layouts.invert = layouts.invert_multi_first
#         return mod2.render(), dbdt1.render(), new_review_clicks, False#, 0
#     raise PreventUpdate


@app.callback(
    Output("inv-log-poll", "n_intervals"),
    Input("invert_all_button", "n_clicks"),
    prevent_initial_call=True,
)
def reset_polling(n):
    return 0

@app.callback(
    [Output('output-data-upload', 'children'),

     m1.output, dbdt1.output, dbdt2.output, rhoa.output,

     Output('process_layout', 'disabled', allow_duplicate=True),
     Output('invert_layout', 'disabled', allow_duplicate=True),
     Output('process_layout', 'n_clicks', allow_duplicate=True),
    #  Output(t1.id, 'children', allow_duplicate=True),
    ],
    Input('upload-data', 'contents'),
    State('process_layout', 'n_clicks'),
    running=[(Output("upload-data", "disabled"), True, False)],
    prevent_initial_call=True
)
def upload_file(contents, current_process_clicks):
    global sesh
    if contents is None:
        raise PreventUpdate
    if contents[0].startswith('data:application/json'):
        import base64
        codec,info = contents[0].split(';')[1].split(',')
        sesh_str = base64.b64decode(info).decode().replace('null', 'None')
        sesh_dict = dict(eval(sesh_str))
        filepath = sesh_dict['save_dir'].replace(' ', '%20')
        return [no_update]*5 + [html.Div(f'File: {sesh_dict['save_dir']}'), f"#load={filepath}"]
    
    sesh.data            = TEMframe.from_zip_content(contents[0])
    sesh.data.history    = ['df_data = TEMframe.from_zip_content("uploaded_data_zip.txt")']
    sesh.data['include'] = sesh.data['inuse_manual'].astype(bool, copy=False).fillna(sesh.data['inuse_auto'])
    sesh.models          = None

    dbdt1.dataframe = sesh.data.copy()
    dbdt2.dataframe = sesh.data.copy()
    rhoa.dataframe = sesh.data.copy()
    Multi_inv.dataframe = sesh.data.copy()
    Sing_inv.dataframe = sesh.data.copy()
    m1.dataframe    = sesh.overview
    mod1.dataframe  = sesh.models
    mod2.dataframe  = sesh.models
    # t1.dataframe = TABLES['overview'].copy()
    new_process_clicks = (current_process_clicks or 0) + 1

    return html.Div("File uploaded successfully."), m1.render(), dbdt1.render(), dbdt2.render(), rhoa.render(), False, False, new_process_clicks#, t1.render()

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
    # ctx = callback_context
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

layout_output_list = [
        m1.output, dbdt1.output, dbdt2.output, rhoa.output, mod2.output,
        
        Output('flex-layout',    'model', allow_duplicate=True),

        Output('upload_layout',  'color',  allow_duplicate=True),
        Output('process_layout', 'color', allow_duplicate=True),
        Output('invert_layout',  'color', allow_duplicate=True),
        Output('review_layout',  'color', allow_duplicate=True), #Output('review_layout', 'disabled', allow_duplicate=True)

        Output('upload_layout',  'disabled',  allow_duplicate=True),
        Output('process_layout', 'disabled', allow_duplicate=True),
        Output('invert_layout',  'disabled', allow_duplicate=True),
        Output('review_layout',  'disabled', allow_duplicate=True), #Output
        Output("current-working-directory", "children"),
        Output('url', 'hash', allow_duplicate=True),
]

def no_update_factory(n):
    return [no_update for _ in range(n)]

@app.callback(
    layout_output_list,     
    Input('url', 'hash'),
    State('flex-layout', 'model'),
    prevent_initial_call=True,
    
)
def handle_url_hash(url_hash, model):
    global sesh
    res = no_update_factory(len(layout_output_list))
    res[-1] = ''
    layout=model
    print(f'url hash: {url_hash}')
    if url_hash.startswith('#load'):
        folder = url_hash.split('=')[1].replace('%20', ' ').replace('%22', '')
        print(f'loading session from folder: {folder}')
        sesh = session.Session.from_folder(folder)
        res[-2] = sesh.save_dir

        if sesh.data is not None:
            dbdt1.dataframe = sesh.data.copy()    
            dbdt2.dataframe = sesh.data.copy()    
            m1.dataframe    = sesh.overview.copy()
            rhoa.dataframe  = sesh.data.copy()    
            Multi_inv.dataframe = sesh.data.copy()
            Sing_inv.dataframe = sesh.data.copy()
            res[0] = m1.render()
            res[1] = dbdt1.render()
            res[2] = dbdt2.render()
            res[3] = rhoa.render()
        
        if sesh.models is not None:
            mod1.dataframe  = sesh.models.copy()
            mod2.dataframe  = sesh.models.copy()
            res[4] = mod2.render()
            # res[5]   = layouts.review
            # res[6]   = 'secondary'
            res[7]   = 'secondary'
            res[8]   = 'secondary'
            res[9]   = 'success'
            res[10]  = False
            res[11]  = False
            res[12]  = False
            res[13]  = False
        else:
            # res[5]   = layouts.data
            # res[6]   = 'secondary'
            res[7]   = 'success'
            res[8]   = 'secondary'
            res[9]   = 'secondary'
            res[10]   = False
            res[11]  = False
            res[12]  = False
            res[13]  = True
    elif url_hash.startswith('#change_working'):
        root = Tk()
        root.withdraw()  # Hide the root window
        folder_path = filedialog.askdirectory(title="Select Working Directory")
        print(folder_path)
        root.destroy()  # Destroy the root window after selection
        if folder_path:
            sesh.save_dir = folder_path + '/' if not folder_path.endswith('/') else folder_path
            print(f'Working directory changed to: {sesh.save_dir}')
            res[-2] = sesh.save_dir
    return res



# import signal
# @app.server.route("/shutdown", methods=["POST"])
# def shutdown():
#     os.kill(os.getpid(), signal.SIGINT)  # Send a signal to the process to terminate


try:
    app.run(port=8050, debug=True, use_reloader=True)
except Exception as e:
    print(f"Error running app: {e}")
# finally:
#     print('closing app, saving data to zip...')
#     sesh.save()

#start msedge --app=http://127.0.0.1:8050/