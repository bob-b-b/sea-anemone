import sys, os
from tkinter import filedialog, Tk


fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)

session_tracker = fpath+'/recent_projects.txt'

from panels import *

from dash import dcc
from dash import Dash, callback_context
from dash.exceptions import PreventUpdate
from dash_bootstrap_components import Button, ButtonGroup, themes
import dash_bootstrap_components as dbc
from dash.dash import no_update

from temframe import TEMframe

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "Sea Anemone"


import os


import os
import base64
import rasterio
import matplotlib
matplotlib.use("Agg")   # non-GUI backend, safe in threads put this at the very top of the file, before importing pyplot

import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import reshape_as_image
from PIL import Image
import plotly.graph_objects as go
import plotly.express as px
from pyproj import Transformer
import pandas as pd
import numpy as np
import math
import json

import matplotlib.cm as cm
import matplotlib.colors as mcolors

from dash import Dash, html, dcc, ctx, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod

from basepanel import Panel, gear_maker, dcc
from temframe import TEMframe

from Sections_plotting import *
from Map_external_layers import *

# --------------------- reading the tiffs and pngs ---------------------
RASTER_FOLDER = r"C:\Users\au679476\Downloads\test_for_map_pngs_tiffs"
# we will put the folder of the session

# # --------------------- Instantiate ---------------------
gis = ScatterMapRenderer(
    dataframe=df,
    settings=settings,
    highlighted=None,
    tiff_path=None,  # leave empty; we'll load on demand
    png_path=None
    )

initial_rasters = gis.build_raster_registry_from_folder(RASTER_FOLDER, include_subfolders=False)
gis.initial_rasters = initial_rasters 




import pandas as pd
# df_overview = pd.DataFrame(columns=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'])

import session

global sesh
sesh = session.Session()


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
u1    = Upload(session_files=session_files)
# t1    = Table(df_overview, id='table_overview', settings=TableSettings('table_overview', visible_columns=[True]*len(df_overview.columns)))
mod1 = ModelGraph(   dataframe=sesh.models )
mod2 = ModelSection( dataframe=sesh.models )


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
            ])
          ], style={'padding': '10px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}
        ),
        dcc.Location(id='url_button'),
      ]
, id='processing_buttons')



#stmod = StartingModel.standard(rho=10.)

Inv_it = Inversion_iterations.standard(misfit=None,rho=10.)

Sing_site = Single_site.standard(rho=10.)

panels = [u1, m1, dbdt1, dbdt2, mod1, mod2, Inv_it, Sing_site, pyInt, gis]
nodes = [node for panel in panels for node in panel.to_nodes()]+[dfl.Tab(id=f'tab-processing_buttons', children=[x]), dfl.Tab(id='tab-panel_list', children=[panel_list])]


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
    dcc.Store(id="vc-level", data="medium"),
    dcc.Store(id="hc-level", data="medium"),
    dcc.Store(id="starting-model", data={"rho": 10.0,"depth": np.logspace(0, np.log10(300), 31).tolist()}),
    dcc.Store(id="vc-single-levels", data=["medium"]),  # default
    html.Div([
        dbc.ButtonGroup([
            dbc.Button("1. Load Data",  id="upload_layout",    color="primary"),
            dbc.Button("2. Process",    id="process_layout",   disabled=True, color="secondary"),
            dbc.Button("3. Invert",     id="invert_layout",    disabled=True, color="secondary"),
            dbc.Button("4. QC",         id="review_layout",    disabled=True, color="secondary"),
            dbc.Button("5. Interpret",  id="interpret_layout", disabled=False, color="secondary"),
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

    df_data = sesh.data

    # Update dataframes with selected sites
    new_df = df_data[df_data['site_id'].isin(selected_sites)]
    dbdt1.dataframe = new_df
    dbdt2.dataframe = new_df

    df_mods = sesh.models
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
                    if (event.key == 'ArrowLeft') {
                        document.getElementById('highlight_prev').click()
                        event.preventDefault()
                        event.stopPropagation()
                    }
                    if (event.key == 'ArrowRight') {
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
        Output("tTEM", "figure", allow_duplicate=True), 
        Output("sounding", "figure", allow_duplicate=True)
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
    df_data = sesh.data
    
    df_data.loc[df_data['data_id'].isin(data_ids), 'inuse_manual'] = inuse
    df_data['include'] = df_data['inuse_manual'].astype(bool, copy=False).fillna(df_data['inuse_auto'])
    dbdt1.dataframe = df_data[df_data['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_data[df_data['site_id'].isin(dbdt2.dataframe['site_id'].unique())]
    return ctx.triggered_id, dbdt2.render(), dbdt1.render()

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
        Output('map', 'figure', allow_duplicate=True),
        Output('model_graph', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('inv_it', 'figure', allow_duplicate=True)
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
        PreventUpdate
    else:
        highlighted += highlight_change
    df_data = sesh.data
    m1.highlighted = highlighted
    mod1.highlighted = highlighted
    dbdt1.dataframe = df_data[df_data['site_id'] == highlighted]
    print('invert layout color:', invert_layout_color)
    if invert_layout_color == 'primary':
        print('will launch an inversion next time')
    

    return ctx.triggered_id, m1.render(), mod1.render(), dbdt1.render(), Inv_it.render()




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
    df_data = sesh.data
    m1.highlighted = site_id
    mod1.highlighted = site_id
    dbdt1.dataframe = df_data[df_data['site_id'] == site_id]
    if invert_layout_color == 'primary':
        df_layers, df_site, _ = df_data.invert_site(site_id)
        # if mod1.dataframe is not None:
        #     df_layers = pd.concat([mod1.dataframe[df_data['site_id'] != site_id], df_layers], ignore_index=True)
        mod1.dataframe = df_layers
        dbdt1.dataframe = df_site
    return m1.render(), mod1.render(), dbdt1.render()

@app.callback(
    Output("starting-model", "data"),
    Input("inv_it", "relayoutData"),
    State("starting-model", "data"),
    prevent_initial_call=True
)
def update_starting_model_from_iterations(relayoutData, data):
    if "shapes[0].x0" not in relayoutData:
        raise PreventUpdate

    rho = float(relayoutData["shapes[0].x0"])
    data["rho"] = rho
    return data


@app.callback(
    Output("vc-level", "data"),
    Output("vc_loose_button", "color"),
    Output("vc_medium_button", "color"),
    Output("vc_tight_button", "color"),
    Output("vc_loose_button", "disabled"),
    Output("vc_medium_button", "disabled"),
    Output("vc_tight_button", "disabled"),
    Input("vc_loose_button", "n_clicks"),
    Input("vc_medium_button", "n_clicks"),
    Input("vc_tight_button", "n_clicks"),
    State("vc-level", "data"),
    prevent_initial_call=True
)
def select_vc_constraint(loose, medium, tight, current):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "vc_loose_button":
        selected = "loose"
    elif trigger == "vc_medium_button":
        selected = "medium"
    elif trigger == "vc_tight_button":
        selected = "tight"
    else:
        selected = current

    def style(name):
        return (
            "primary" if selected == name else "secondary",
            selected == name
        )

    loose_color, loose_disabled   = style("loose")
    med_color, med_disabled       = style("medium")
    tight_color, tight_disabled   = style("tight")

    return (
        selected,
        loose_color, med_color, tight_color,
        loose_disabled, med_disabled, tight_disabled
    )
@app.callback(
    Output("hc-level", "data"),
    Output("hc_loose_button", "color"),
    Output("hc_medium_button", "color"),
    Output("hc_tight_button", "color"),
    Output("hc_loose_button", "disabled"),
    Output("hc_medium_button", "disabled"),
    Output("hc_tight_button", "disabled"),
    Input("hc_loose_button", "n_clicks"),
    Input("hc_medium_button", "n_clicks"),
    Input("hc_tight_button", "n_clicks"),
    State("hc-level", "data"),
    prevent_initial_call=True
)
def select_hc_constraint(loose, medium, tight, current):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger = ctx.triggered[0]["prop_id"].split(".")[0]

    if trigger == "hc_loose_button":
        selected = "loose"
    elif trigger == "hc_medium_button":
        selected = "medium"
    elif trigger == "hc_tight_button":
        selected = "tight"
    else:
        selected = current

    def style(name):
        return (
            "primary" if selected == name else "secondary",
            selected == name
        )

    loose_color, loose_disabled   = style("loose")
    med_color, med_disabled       = style("medium")
    tight_color, tight_disabled   = style("tight")

    return (
        selected,
        loose_color, med_color, tight_color,
        loose_disabled, med_disabled, tight_disabled
    )

@app.callback(
    Output("vc-single-levels", "data"),
    Output("vc_sing_loose_button", "color"),
    Output("vc_sing_medium_button", "color"), 
    Output("vc_sing_tight_button", "color"),
    Input("vc_sing_loose_button", "n_clicks"),
    Input("vc_sing_medium_button", "n_clicks"),
    Input("vc_sing_tight_button", "n_clicks"),
    State("vc-single-levels", "data"),
    prevent_initial_call=True
)
def toggle_single_site_vc(loose, medium, tight, active):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    button = ctx.triggered_id.replace("vc_sing_", "").replace("_button", "")

    if button in active:
        active.remove(button)
    else:
        active.append(button)

    def color(name):
        return "primary" if name in active else "secondary"

    return (
        active,
        color("loose"),
        color("medium"),
        color("tight"),
    )


@app.callback(
    [
        Output('model_section', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('review_layout', 'n_clicks', allow_duplicate=True),
        Output('review_layout', 'disabled', allow_duplicate=True),
    ],
    Input('invert_all_button', 'n_clicks'),
    State('review_layout', 'n_clicks'),  # Add this state to get current value
    State("vc-level", "data"),
    State("hc-level", "data"),
    State("starting-model", "data"),
    running=[(Output("invert_all_button", "disabled"), True, False),
    (Output("invert_selected_button", "disabled"), True, False), 
    (Output("inv-log-poll", "disabled"), False, True),    
    (Output("vc_loose_button", "disabled"), True, False),
    (Output("vc_medium_button", "disabled"), True, False),
    (Output("vc_tight_button", "disabled"), True, False),
    (Output("hc_loose_button", "disabled"), True, False),
    (Output("hc_medium_button", "disabled"), True, False),
    (Output("hc_tight_button", "disabled"), True, False),
    (Output('reset_inv_model_button', "disabled"), True, False)],
    prevent_initial_call=True
)
def launch_inversion(n_clicks, current_review_clicks, vc_level,hc_level,starting_model):
    if n_clicks:
        from torch import from_numpy, tensor
        print('starting model:', starting_model["rho"])
        rho = tensor(starting_model["rho"]).repeat(len(starting_model["depth"]))
        z   = tensor(starting_model["depth"][:-1])

        if vc_level == "loose":
            Vert = 5.0
        elif vc_level == "medium":
            Vert = 0.5
        elif vc_level == "tight":
            Vert = 0.1

        if hc_level == "loose":
            Horz = 5.0
        elif hc_level == "medium":
            Horz = 0.6
        elif hc_level == "tight":
            Horz = 0.3
        res_start                        = LogResistivity.smooth(rho,z) 
        sesh.models, sesh.data = sesh.data.invert(res_start,vc = Vert, hc = Horz)
        mod1.dataframe                   = sesh.models.copy()
        mod2.dataframe                   = sesh.models.copy()
        dbdt1.dataframe                  = sesh.data.copy()
        dbdt2.dataframe                  = sesh.data.copy()
        new_review_clicks = (current_review_clicks or 0) + 1
        layouts.invert = layouts.invert_multi_first
        return mod2.render(), dbdt1.render(), new_review_clicks, False#, 0
    raise PreventUpdate

@app.callback(
    Output("inv-single", "figure", allow_duplicate=True),
    Input("invert_single_button", "n_clicks"),
    State("vc-levels", "data"),
    State("starting-model", "data"),
    prevent_initial_call=True
)
def invert_single_site(n_clicks, vc_levels, starting_model):
    curves = []

    rho = torch.tensor(starting_model["rho"]).repeat(len(starting_model["depth"]))
    z   = torch.tensor(starting_model["depth"][:-1])

    for vc in vc_levels:
        Vert = {"loose": 1.0, "medium": 0.5, "tight": 0.1}[vc]
        res_start = LogResistivity.smooth(rho, z)
        df_layers, _ = TABLES["data"].invert_site(
            site_id=current_site,
            res_start=res_start,
            vc=Vert,
            hc=default_hc
        )

        curves.append((vc, df_layers))

    return Sing_site.render(curves)

@app.callback(
    Output("inv-log-poll", "n_intervals"),
    Input("invert_all_button", "n_clicks"),
    prevent_initial_call=True,
)
def reset_polling(n):
    return 0

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
    running=[(Output("upload-data", "disabled"), True, False)],
    prevent_initial_call=True
)
def upload_file(contents, current_process_clicks):
    if contents is None:
        raise PreventUpdate
    sesh.data            = TEMframe.from_zip_content(contents[0])
    sesh.data.history    = ['df_data = TEMframe.from_zip_content("uploaded_data_zip.txt")']
    sesh.data['include'] = sesh.data['inuse_manual'].astype(bool, copy=False).fillna(sesh.data['inuse_auto'])
    sesh.models          = None

    dbdt1.dataframe = sesh.data.copy()
    dbdt2.dataframe = sesh.data.copy()
    m1.dataframe    = sesh.overview
    mod1.dataframe  = sesh.models
    mod2.dataframe  = sesh.models
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
        Output('interpret_layout', 'color'),
    ],
    [
        State('flex-layout', 'model'),
        Input("upload_layout", 'n_clicks'),
        Input("process_layout", 'n_clicks'),
        Input("invert_layout", 'n_clicks'),
        Input("review_layout", 'n_clicks'),
        Input("interpret_layout", 'n_clicks'),
    ],
    prevent_initial_call=True
)
def update_layout(model, load_clicks, process_clicks, invert_clicks, review_clicks, interpret_clicks):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate
    
    # Get the ID of the button that was clicked
    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    
    if button_id == "upload_layout":
        return layouts.upload, 'primary', 'secondary', 'secondary', 'secondary', 'secondary'
    elif button_id == "process_layout":
        return layouts.data, 'secondary', 'primary', 'secondary', 'secondary', 'secondary'
    elif button_id == "invert_layout":
        return layouts.invert, 'secondary', 'secondary', 'primary', 'secondary', 'secondary'
    elif button_id == "review_layout":
        return layouts.review, 'secondary', 'secondary', 'secondary', 'primary', 'secondary'
    elif button_id == 'interpret_layout':
        return layouts.interpret, 'secondary', 'secondary', 'secondary', 'secondary', 'primary'
    return model, 'secondary', 'secondary', 'secondary', 'secondary', 'secondary'


# @app.callback(
#     [
#         
#         Output('url', 'hash', allow_duplicate=True)
#     ],
#     Input('url', 'hash'),
#     State("current-working-directory", "children"),
#     prevent_initial_call=True,
# )
# def handle_url_hash(url_hash, current_working_directory):
#     if url_hash.startswith('#change_working'):
#         root = Tk()
#         root.withdraw()  # Hide the root window
#         folder_path = filedialog.askdirectory(title="Select Working Directory")
#         print(folder_path)
#         root.destroy()  # Destroy the root window after selection
#         sesh.save_dir = folder_path + '/' if not folder_path.endswith('/') else folder_path
#         return folder_path, ''
#     else:
#         return current_working_directory, ''

layout_output_list = [
        Output('map', 'figure', allow_duplicate=True),
        Output('sounding', 'figure', allow_duplicate=True),
        Output('tTEM', 'figure', allow_duplicate=True),
        Output('model_section', 'figure', allow_duplicate=True),
        
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
        #sesh.
        dbdt1.dataframe = sesh.data.copy()     if sesh.data is not None else None
        dbdt2.dataframe = sesh.data.copy()     if sesh.data is not None else None
        m1.dataframe    = sesh.overview.copy() if sesh.data is not None else None
        mod1.dataframe  = sesh.models.copy()   if sesh.models is not None else None
        mod2.dataframe  = sesh.models.copy()   if sesh.models is not None else None

        res[0] = m1.render()
        res[1] = dbdt1.render()
        res[2] = dbdt2.render()
        res[3] = mod2.render()

        if sesh.models is not None:
            res[4]   = layouts.review
            res[5]   = 'secondary'
            res[6]   = 'secondary'
            res[7]   = 'secondary'
            res[8]   = 'primary'
            res[9]   = False
            res[10]  = False
            res[11]  = False
            res[12]  = False
        else:
            res[4]   = layouts.data
            res[5]   = 'secondary'
            res[6]   = 'primary'
            res[7]   = 'secondary'
            res[8]   = 'secondary'
            res[9]   = False
            res[10]  = False
            res[11]  = False
            res[12]  = True
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


import sys
import io
import traceback
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


# import signal
# @app.server.route("/shutdown", methods=["POST"])
# def shutdown():
#     os.kill(os.getpid(), signal.SIGINT)  # Send a signal to the process to terminate


# try:
#     app.run(port=8050, debug=True, use_reloader=True)
# except Exception as e:
#     print(f"Error running app: {e}")

# finally:
#     print('closing app, saving data to zip...')
    # sesh.save()

# #start msedge --app=http://127.0.0.1:8050/

# --------------------- starting the app - needs to be after the readings of tiffs and pngs! ---------------------

# app = Dash(__name__, suppress_callback_exceptions=True)
# app.title = "sea anemone"

# def serve_layout():
#     return gis.initialize()  # <-- no args

# app.layout = serve_layout

# Register the callback HERE (outside the class)
# CALLBACK FOR ALT+LEFT CLICK + CTRL

app.clientside_callback(
    """
    function(clickData){ 
        // 3. Only trigger if Alt is held down
        if (!window._keyTracker.alt) {
            return window.dash_clientside.no_update;
        }

        // 4. Extract Data from Click Point
        const pt = clickData.points[0];
        let cd = pt.customdata;
        
        let extractedId = null;
        let extractedType = "tem"; // Default type

        // 5. Robust Extraction Logic
        // We drill down through arrays because Plotly structures customdata differently 
        // for points vs. fills (Scatter 'toself')
        if (cd !== undefined && cd !== null) {
            let dataArray = cd;
            
            // If it's a nested array (e.g., [[id, dist, type]]), grab the inner one
            if (Array.isArray(dataArray) && Array.isArray(dataArray[0])) {
                dataArray = dataArray[0];
            }

            // At this point, dataArray should be [id, dist, type] or [id]
            if (Array.isArray(dataArray)) {
                extractedId = dataArray[0];
                
                // If the 3rd element is "borehole", update the type
                if (dataArray.length >= 3 && dataArray[2] === "borehole") {
                    extractedType = "borehole";
                }
            } else {
                // Fallback for simple single-value customdata
                extractedId = dataArray;
            }
        }

        // 6. Final Debug Log (Check your Browser Console with F12)
        console.log("🎯 Alt+Click Detected:", {
            id: extractedId,
            type: extractedType,
            multi: window._keyTracker.ctrl
        });

        // 7. Return to Python Store
        return {
            "index": extractedId,
            "type": extractedType,
            "multi": window._keyTracker.ctrl,
            "timestamp": Date.now()
        };
    }
    """,
    Output("right-click-index-store", "data"),
    Input("profile-plot_main", "clickData"),
    prevent_initial_call=True
)

# --------------------- Layers Menu ---------------------
# --------------------- Toggle the main layers panel ---------------------
@app.callback(
    Output("layers-panel", "style"),    
    Input("layers-toggle", "n_clicks"),
    State("layers-panel", "style"),
)
def toggle_layers_panel(n, style):
    if not n:
        return style
    return {**style,"display": "block" if style["display"] == "none" else "none",}

# --------------------- Toggle 3-dot menu per layer ---------------------
@app.callback(
    Output({"type": "layer-menu", "layer": MATCH}, "style"),
    Input({"type": "layer-menu-btn", "layer": MATCH}, "n_clicks"),
    State({"type": "layer-menu", "layer": MATCH}, "style"),)

def toggle_layer_menu(n, style):
    if not n:
        return style
    return {**style,"display": "block" if style["display"] == "none" else "none",}

# --------------------- Collect active layers (and boreholes) ---------------------
@app.callback(
    Output("layers-store", "data"),
    Output("raster-busy-store", "data"),
    Output("raster-load-trigger", "data"),
    Input({"type": "layer-check", "layer": ALL}, "value"),
    State({"type": "layer-check", "layer": ALL}, "id"),
    State("layers-store", "data"),
    State("raster-load-trigger", "data"),
    prevent_initial_call=True
)

def collect_layers_and_trigger(values, ids, prev_layers, trig_count):
    prev_layers = prev_layers or []
    trig_count = trig_count or 0

    # compute new active layers
    active_layers = [i["layer"] for v, i in zip(values, ids) if v and "on" in v]

    # detect "raster turned ON" event
    prev_set = set(prev_layers)
    new_set = set(active_layers)
    turned_on = list(new_set - prev_set)

    raster_turned_on = any(
        isinstance(x, str) and (x.startswith("tiff_") or x.startswith("png_"))
        for x in turned_on
    )

    if raster_turned_on:
        # show overlay immediately + kick heavy callback
        return active_layers, True, trig_count + 1

    # otherwise: just update layers; don't touch busy/trigger
    return active_layers, no_update, no_update

# --------------------- Collect opacities ---------------------
@app.callback(
    Output("opacity-store", "data"),
    Input({"type": "layer-opacity", "layer": ALL}, "value"),
    State({"type": "layer-opacity", "layer": ALL}, "id"),)

def collect_opacities(values, ids):    
    return {i["layer"]: v for v, i in zip(values, ids)}

# --------------------- attributes sync ---------------------
@app.callback(
    Output("points-attr", "options"),
    Output("points-attr", "value"),
    Output("points-filter", "options"),
    Output("points-filter", "value"),
    Output("points-color-map-store", "data"),
    Output("points-filters-by-attr-store", "data"),

    Input("map-settings-store", "data"),     # so it can initialize from settings
    Input("points-attr", "value"),           # user changes attribute
    Input("points-filter", "value"),         # user changes checklist

    State("points-attr", "options"),
    State("points-filters-by-attr-store", "data"),
    State("points-available-attrs-store", "data"),
    prevent_initial_call=False,)

def sync_points_ui(settings, attr_value, filter_value,
                   existing_attr_options, filters_by_attr, existing_attrs):

    if df is None:
        return [], no_update, [], [], {}, (filters_by_attr or {})

    local_df = pd.DataFrame(df)
    filters_by_attr = filters_by_attr or {}

    # ---- available attributes come ONLY from existing_attrs ----
    existing_attrs = existing_attrs or []
    available_attrs = [a for a in existing_attrs if a in local_df.columns]

    attr_options = [{"label": a, "value": a} for a in available_attrs]

    # ---- decide default attribute ----
    default_attr = None
    if settings and isinstance(settings, dict):
        default_attr = settings.get("plot_attribute")

    if not default_attr or default_attr not in available_attrs:
        default_attr = "date" if "date" in available_attrs else (available_attrs[0] if available_attrs else None)

    # what triggered?
    trig = ctx.triggered_id

    # ---- choose current attribute ----
    current_attr = attr_value if attr_value in available_attrs else default_attr

    if not current_attr:
        return attr_options, no_update, [], [], {}, filters_by_attr

    # ---- compute unique cleaned values (must match renderer cleaning) ----
    series_cleaned = (local_df[current_attr].astype(str)
                      .str.replace(r"\.0$", "", regex=True)
                      .str.strip())
    unique_vals = sorted(series_cleaned.unique().tolist())

    filter_options = [{"label": str(v), "value": str(v)} for v in unique_vals]
    all_values = [str(v) for v in unique_vals]

    # ---- numeric vs categorical ----
    is_numeric = pd.api.types.is_numeric_dtype(local_df[current_attr]) and current_attr != "date"
    if is_numeric:
        color_map = {}  # numeric uses colorscale in renderer
    else:
        palette = px.colors.qualitative.Light24
        color_map = {val: palette[i % len(palette)] for i, val in enumerate(unique_vals)}

    # ---- decide checklist value & persist memory ----
    if trig == "points-filter":
        selected = filter_value or []
        filters_by_attr[current_attr] = selected
        checklist_value = selected
    else:
        restored = filters_by_attr.get(current_attr)
        if restored is None:
            checklist_value = all_values
        else:
            restored = [v for v in restored if v in set(all_values)]
            checklist_value = restored if restored else all_values

        filters_by_attr[current_attr] = checklist_value

    return attr_options,current_attr,filter_options,checklist_value,color_map,filters_by_attr

# --------------------- Store zoom / center ---------------------
@app.callback(
    Output("map-view-store", "data"),   
    Input(gis.id, "relayoutData"),
    State("map-view-store", "data"),
    prevent_initial_call=True,)

def update_map_view(relayout, view):

    if not relayout:
        return no_update

    # store bbox
    if "map._derived" in relayout and "coordinates" in relayout["map._derived"]:
        coords = relayout["map._derived"]["coordinates"]

        print("✔ Updated BBOX:", coords)

        # keep previous center, zoom if available
        center = relayout.get("map.center", (view or {}).get("center"))
        zoom   = relayout.get("map.zoom",   (view or {}).get("zoom"))

        return {
            "bbox": coords,
            "center": center,
            "zoom": zoom,
        }

    return no_update

# --------------------- Toggle the profiles Panel ---------------------
@app.callback(
    Output("profiles-panel", "style"),
    Input("profiles-toggle", "n_clicks"),
    State("profiles-panel", "style"),
    prevent_initial_call=True
)
def toggle_profiles_menu(n, current_style):
    if n:
        display = "block" if current_style.get("display") == "none" else "none"
        current_style["display"] = display
        return current_style
    return current_style

# --------------------- toggle the Section dropdown ---------------------
@app.callback(
    Output("section-panel", "style", allow_duplicate=True),
    Input("section-toggle", "n_clicks"),
    State("section-panel", "style"),
    prevent_initial_call=True,
)
def toggle_section_panel(n, style):
    if not n:
        return style
    new = style.copy()
    new["display"] = "block" if style["display"] == "none" else "none"
    return new

# --------------------- selecting a section mode ---------------------
@app.callback(
    Output("section-mode-store", "data"),
    Input({"type": "section-option", "mode": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def select_section_mode(n_clicks):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
    mode = eval(trigger_id)["mode"]

    print("MODE SELECTED:", mode)

    return mode

# --------------------- auto-close callback for sections ---------------------
@app.callback(
    Output("section-panel", "style", allow_duplicate=True),
    Input({"type": "section-option", "mode": ALL}, "n_clicks"),
    State("section-panel", "style"),
    prevent_initial_call=True,
)
def close_section_panel(n_clicks, style):

    # Prevent triggering when all are None or zero
    if not any(n_clicks):
        return no_update

    new = style.copy()
    new["display"] = "none"
    # print("Section panel closed.")
    return new


# --------------------- auto-close callback for layers ---------------------
@app.callback(
    Output("layers-panel", "style", allow_duplicate=True),
    Input({"type": "layer-check", "layer": ALL}, "value"),   # checkboxes
    Input({"type": "layer-opacity", "layer": ALL}, "value"),    # opacity sliders
    Input({"type": "layer-menu-btn", "layer": ALL}, "n_clicks"),# 3-dot menus
    State("layers-panel", "style"),
    prevent_initial_call=True,
)
def auto_close_layers(layer_values, opacity_values, menu_clicks, style):

    # Check for ANY triggered change:
    changed = False

    # Layer checkbox values (lists)
    if layer_values and any(v is not None for v in layer_values):
        changed = True

    # Opacity slider values (floats)
    if opacity_values and any(v is not None for v in opacity_values):
        changed = True

    # 3-dot menu clicks (ints)
    if menu_clicks and any((x or 0) > 0 for x in menu_clicks):
        changed = True

    if not changed:
        return no_update

    # Close panel
    new = style.copy()
    new["display"] = "none"
    # print(">> Layers panel auto-closed")

    return new




    # Input("line-final-store", "data"),
    # Input("section-mode-store", "data"),
    # Input("selected-line-index", "data"),
    # State("map-view-store", "data"),
# --------------------- live profile MULTI LINE plot callback ---------------------
@app.callback(
    Output("profile-plot-container", "children"),
    Output("profile-plot-container", "style"),

    Output("profile-busy-store", "data", allow_duplicate=True),
    Input("profile-load-trigger", "data"), 

    State("line-final-store", "data"),
    State("section-mode-store", "data"),
    State("selected-line-index", "data"),
    State("map-view-store", "data"),

    State("profile-busy-store", "data"),
    prevent_initial_call=True
)

def update_section(_trig, lines, mode, selected_idx, view, busy_state):
    t0 = time.perf_counter()
    busy_state = busy_state or {"busy": True, "since": time.time()}

    base_style = {"flex": "1",
        "position": "relative",
        "width": "50%","height": "75%",
        "minHeight": 0,"margin": "auto",
        "background": "white","borderRadius": "8px","boxShadow": "0 0 10px rgba(0,0,0,0.15)",
        "padding": "5px","boxSizing": "border-box","overflow": "hidden",
        "display": "flex","flexDirection": "column",}
    
    if not lines:
            return [], base_style,False   #   [dcc.Graph(id="profile-plot_main", figure=go.Figure(), style={"height":"100%","width":"100%"})]
    
    try:
        current_line = lines[selected_idx]
    except:
        current_line = lines[-1]
    
    print(f"[profile] start trig={_trig} n_lines={len(lines)} mode={mode} n_pts={len(current_line)}")
    
    # busy = True

    # 1. Gather all data
    y_depth = np.array(df["Depths"].iloc[0])[:-1]


    all_x, interp_lons, interp_lats = get_polyline_profile(current_line, df, resolution_m=50)
    
    # Get Stations and Boreholes
    stations_on_line = get_station_projections(current_line, df, search_radius_m=Settings.radius)
    if bh_data is not None:
        bh_projections = get_borehole_projections(current_line, bh_data, view, search_radius_m=Settings.radius)

    # 2. FAILSAFE: If nothing is near the line, show a message
    if not stations_on_line and not bh_projections:
        msg = f"No data (stations or boreholes) found within {Settings.radius}m"
        return go.Figure().add_annotation(text=msg, showarrow=False), base_style,{"busy": False, "since": ...}

    # 3. Calculate Path Elevations (Terrain)
    if stations_on_line:
        st_x = [s['dist_x'] for s in stations_on_line]
        st_z = [s['elev'] for s in stations_on_line]
        
        # If only 1 station exists, np.interp needs a fallback
        if len(st_x) == 1:
            path_elevations = np.full_like(all_x, st_z[0])
        else:
            path_elevations = np.interp(all_x, st_x, st_z)
    else:
        # Fallback if only boreholes exist: use borehole elevation as flat terrain
        if bh_projections:
            avg_elev = np.mean([b['elev'] for b in bh_projections])
            path_elevations = np.full_like(all_x, avg_elev)
        else:
            path_elevations = np.zeros_like(all_x)

    # 4. Initialize Figure based on Mode
    if mode == "blocky":
        if stations_on_line:
            fig = create_blocky_polygons(stations_on_line, y_depth, bar_width=30)
        else:
            fig = go.Figure() # Start empty, add boreholes below
            
    elif mode == "interp":
        samples = np.vstack([interp_lons, interp_lats]).T
        res_models, elevations, _, _ = interpolate_nearest(df, samples, radius=Settings.radius)
        fig = plot_section_topographic(all_x, y_depth, res_models, elev=path_elevations)
        
    elif mode == "combined":
        samples = np.vstack([interp_lons, interp_lats]).T
        res_models, elevations, _, _ = interpolate_nearest(df, samples, radius=Settings.radius)
        fig = combine_sections_final(all_x, y_depth, res_models, path_elevations, stations_on_line)

    # 5. Add Boreholes
    if bh_projections:
        fig = add_boreholes_to_fig(fig, bh_projections, rock_color_map)

    # 6. ADJUST AXIS BOUNDS (The Fix for Zoom)
    # Collect all X coordinates from both sources
    all_x_vals = list(all_x)
    if stations_on_line:
        all_x_vals.extend([s['dist_x'] for s in stations_on_line])
    if bh_projections:
        # Include the left and right edges of the borehole columns
        for b in bh_projections:
            all_x_vals.append(b['dist_x'] - 20) # 20m margin
            all_x_vals.append(b['dist_x'] + 20)

    x_min, x_max = min(all_x_vals), max(all_x_vals)
    padding = (x_max - x_min) * 0.1 if x_max != x_min else 50
    
    fig.update_layout(
        xaxis=dict(range=[x_min - padding, x_max + padding]),
        hovermode='closest')
    
    show_colorbar = mode in ["blocky", "interp", "combined"] and len(stations_on_line) > 0

    # prof_plot_height = 300

    graph =  html.Div(
        dcc.Graph(id="profile-plot_main", figure=fig, style={"height": "100%", "width": "100%"},
        config={"doubleClick": "reset+autosize", "doubleClickDelay": 200, "displayModeBar": True},),  
        style={"flex": "1 1 auto", "minHeight": 0, "width": "100%"},)

    if show_colorbar:
        # vertical colorbar
        # legend_bar = create_geologic_colorbar(settings.res_min, settings.res_max, plot_height = prof_plot_height)
        # content = html.Div(
        #     [
        #         html.Div(graph, style={"flex": "1", "minWidth": "0", "height": "100%"}),
        #         html.Div(legend_bar, style={"width": "70px", "display": "flex", 
        #                                     "justifyContent": "center","alignItems": "center",
        #                                     "height": "100%",
        #                                     }
        #                 )
        #     ],
        #     style={"display": "flex", "height": "100%", "width": "100%"}
        # )


        legend_bar = create_geologic_colorbar_horizontal(settings.res_min,settings.res_max, bar_height=18)

        content = html.Div(
            [html.Div(graph), #, style={"flex": "1", "minHeight": 0}
                html.Div(legend_bar,style={"width": "80%", "margin": "0 auto", "marginTop": "8px",},),
            ],
            style={
                "display": "flex","flexDirection": "column",
                "height": "100%","width": "100%","minHeight": 0, 
            },
        )

        dt = time.perf_counter() - t0
        print(f"[profile] done trig={_trig} in {dt:.2f}s")

        return [content], base_style, {"busy": False, "since": busy_state.get("since", time.time())} #False
    else:
        content = html.Div(
                        html.Div(graph),
                        style={
                            "display": "flex","flexDirection": "column",
                            "height": "100%","width": "100%","minHeight": 0,  
                        },
                    )
        return [content], base_style, {"busy": False, "since": busy_state.get("since", time.time())} #False


    # return [graph], base_style


# --------------------- MULTI LINE select profile dropdown and clear all or selected ---------------------
@app.callback(
    Output("line-final-store", "data", allow_duplicate=True),
    Output("profile-list-container", "children"),
    Output("selected-line-index", "data"),
    Input("line-final-store", "data"),
    Input("clear-selected-btn", "n_clicks"),
    Input("clear-all-btn", "n_clicks"),
    Input({"type": "view-line-btn", "index": ALL}, "n_clicks"), 
    State({"type": "del-check", "index": ALL}, "value"),        
    State("selected-line-index", "data"),
    prevent_initial_call=True
)
def master_line_controller(lines, clear_sel_n, clear_all_n, view_clicks, check_states, current_idx):
    ctx = callback_context
    if not ctx.triggered:
        return no_update

    trigger_id = ctx.triggered[0]["prop_id"]
    new_lines = lines if lines else []
    new_active_idx = current_idx if current_idx is not None else 0

    # --- ACTION: CLEAR ALL ---
    if "clear-all-btn" in trigger_id:
        return [], [], 0

    # --- ACTION: CLEAR SELECTED ---
    if "clear-selected-btn" in trigger_id:
        indices_to_remove = [i for i, val in enumerate(check_states) if val]
        new_lines = [line for i, line in enumerate(new_lines) if i not in indices_to_remove]
        new_active_idx = max(0, len(new_lines) - 1)
        # We return the new lines, and the UI will rebuild in the next step

    # --- ACTION: CHANGE VIEW (👁️) ---
    if "view-line-btn" in trigger_id:
        prop_dict = eval(trigger_id.split(".")[0])
        new_active_idx = prop_dict["index"]

    # --- ACTION: NEW LINE ADDED ---
    if "line-final-store.data" in trigger_id:
        new_active_idx = len(new_lines) - 1

    # --- UI GENERATION ---
    # We rebuild the list so the "Active" row is highlighted
    rows = []
    for i in range(len(new_lines)):
        is_active = (i == new_active_idx)
        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "padding": "8px",
                "borderBottom": "1px solid #ddd",
                "backgroundColor": "#D1ECF1" if is_active else "transparent", # Light blue highlight
                "borderRadius": "4px", "marginBottom": "2px"
            },
            children=[
                html.Span(f"Profile {i+1}", style={
                    "flex": 1, "fontSize": "13px", 
                    "fontWeight": "bold" if is_active else "normal"
                }),
                # Eye icon button
                html.Button(
                    "👁️", 
                    id={"type": "view-line-btn", "index": i},
                    style={
                        "border": "none", "background": "none", "cursor": "pointer", 
                        "fontSize": "16px", "marginRight": "10px",
                        "opacity": "1" if is_active else "0.3"
                    }
                ),
                # Delete checkbox
                dcc.Checklist(
                    id={"type": "del-check", "index": i},
                    options=[{"label": "", "value": 1}],
                    value=[],
                )
            ]
        ))

    return new_lines, rows, new_active_idx

# --------------------- draw lines and/or multilines ---------------------
@app.callback(
    Output("line-final-store", "data", allow_duplicate=True),
    Output("zoom-warning-dialog", "displayed"), # To trigger an alert message
    Input(gis.id, "relayoutData"),
    State("map-view-store", "data"),
    State("line-final-store", "data"),
    prevent_initial_call=True
    )

def on_draw_polyline(relayout, view, store): #, current_fig
    if not relayout or "shapes" not in relayout:
        return no_update, False

    if not view or "bbox" not in view:
            print("⛔ on_draw blocked — bbox not ready yet")            
           
            return no_update, True 

    # Get the most recently drawn shape
    shape = relayout["shapes"][-1]
    
    # 1. Handle Multi-point Polyline (path)
    if "path" in shape:
        path_str = shape["path"]
        # Use our robust regex parser from earlier
        new_line_coords = parse_polyline_path(path_str, view=view)
    
    # 2. Fallback for simple two-point lines (x0, y0, x1, y1)
    elif "x0" in shape:
        p0 = paper_to_geo(shape["x0"], shape["y0"], view)
        p1 = paper_to_geo(shape["x1"], shape["y1"], view)
        new_line_coords = [p0, p1]    
    else:
        return no_update

    if not new_line_coords or None in new_line_coords:
        return no_update, "Coordinate parsing failed."

    # Initialize store if empty
    current_store = store if store is not None else []
    # Append the new list of coordinates [[lon1, lat1], [lon2, lat2], ...]
    current_store.append(new_line_coords)

    print(f"✔ Added Polyline with {len(new_line_coords)} points")
    return current_store, False 

# --------------------- hover on map ---------------------
@app.callback(
    Output("map-hover-marker-store", "data"),
    Input("profile-plot_main", "hoverData"),
    State("line-final-store", "data"),
    State("selected-line-index", "data"),
    prevent_initial_call=True
)

def sync_hover_to_map(hoverData, lines, selected_idx):
    if not hoverData or 'points' not in hoverData:
        return None

    try:
        pt = hoverData['points'][0]
        
        # 1. Try to get 'x'
        dist_m = pt.get('x')
        
        # 2. If 'x' is missing or None, look into 'customdata'
        if dist_m is None and 'customdata' in pt:
            val = pt['customdata']
            # If it's a list (like your debug data shows), take the first item
            dist_m = val[1] if isinstance(val, list) else val

        if dist_m is None or not lines:
            return None

        # 3. Standard line lookup logic
        try:
            current_line = lines[selected_idx]
        except (IndexError, TypeError):
            current_line = lines[-1] 

        # 4. Math: Distance -> Lon/Lat
        geo_pt = get_geo_at_distance(current_line, float(dist_m))
        return geo_pt

    except Exception as e:
        print(f"⚠️ Sync Error: {e}")
        return None
    
# # --------------------- #  GOOD CALLBACK FOR ALT+LEFT CLICK + CTRL FOR click on models ---------------------
@app.callback(
    Output("window-container", "children"),
    Output("combined-window-store", "data"),
    Input("right-click-index-store", "data"),
    Input({"type": "close-window", "index": ALL}, "n_clicks"),
    State("window-container", "children"),
    State("combined-window-store", "data"),
    State("line-final-store", "data"),        # To get current line geometry
    State("selected-line-index", "data"),     # To know which line is active
    prevent_initial_call=True
)

def manage_windows(click_data, n_closes, current_windows, combined_state,all_lines, selected_idx):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update

    trigger = ctx.triggered[0]["prop_id"]
    windows = list(current_windows or [])
    # combined_state stores: {"window_id": str, "items": [[id, type], ...]}
    combined_state = combined_state or {"window_id": None, "items": []}
    width_step = "550px"
    height_step ="900px"
    bh_projections = []
    if all_lines and selected_idx is not None:
        try:
            current_line = all_lines[selected_idx]
            # bh_data is your global dataframe/list of all boreholes
            if bh_data is not None:
                # view='profile' usually, search_radius from your Settings
                bh_projections = get_borehole_projections(current_line, bh_data, view='profile', search_radius_m=Settings.radius)
        except Exception as e:
            print(f"⚠️ Borehole Projection Error: {e}")    
    
    # --- 1. HANDLE NEW CLICKS (ALT or CTRL+ALT) ---
    if "right-click-index-store" in trigger:
        if not click_data:
            return no_update, no_update

        idx = click_data.get("index")
        item_type = click_data.get("type", "tem") # 'tem' or 'borehole'
        is_combined = bool(click_data.get("multi"))
        ts = click_data.get("timestamp")

        # A) ALT-ONLY: Create a new independent window
        if not is_combined:
            if idx is None:  # Safety check for empty clicks
                return no_update, no_update
            
            new_id = f"win-{idx}-{ts}"
            if item_type == "borehole":
                # Use your existing borehole logic
                fig = build_combined_borehole_figure([idx], bh_projections, rock_color_map)
                title = f"Borehole Log: {idx}"
            else:
                try:
                    row_data = None
                    if idx in df.index:
                        row_data = df.loc[idx] if idx in df.index else df.iloc[int(idx)]
                    else:
                        int_idx = int(idx)
                        if 0 <= int_idx < len(df):
                            row_data = df.iloc[int_idx]
                except (ValueError, TypeError):
                    row_data = None

                if row_data is not None:
                    fig = generate_res_step_graph(row_data, idx)
                    title = f"TEM Sounding: {idx}"
                else:
                    # If click was on interpolation/background, just do nothing
                    return no_update, no_update

            windows.append(create_draggable_window(new_id, title, fig, width=width_step, height=height_step))
            return windows, combined_state

        # B) CTRL+ALT: Add to Comparison Window
        else:
            if not combined_state.get("window_id"):
                combined_state["window_id"] = f"win-comparison-{ts}"
                combined_state["items"] = []

            # Add to list if not already there
            if [idx, item_type] not in combined_state["items"]:
                combined_state["items"].append([idx, item_type])

            items = combined_state["items"]
            tem_ids = [it[0] for it in items if it[1] == "tem"]
            bh_ids = [it[0] for it in items if it[1] == "borehole"]

            # GENERATE CONTENT BASED ON SELECTION
            # Scenario: Only TEMs selected -> Overlay Plot
            if len(bh_ids) == 0:
                fig = build_combined_step_figure(df, tem_ids, use_elevation=True)
                content = dcc.Graph(figure=fig, style={"height": "100%"})
                title = f"Combined TEM Models ({len(tem_ids)})"
                # width = "650px"

            # Scenario: Only Boreholes selected -> Side-by-Side Logs
            elif len(tem_ids) == 0:
                fig = build_combined_borehole_figure(bh_ids, bh_projections, rock_color_map)
                content = dcc.Graph(figure=fig, style={"height": "100%"})
                title = f"Borehole Comparison ({len(bh_ids)})"
                # width = "650px"

            # Scenario: BOTH selected -> Side-by-Side Comparison (TEM vs BH)
            else:
                tem_fig = build_combined_step_figure(df, tem_ids, use_elevation=True)
                bh_fig = build_combined_borehole_figure(bh_ids, bh_projections, rock_color_map)
                
                # OPTIONAL: Align Y-Axes if using Elevation
                content = html.Div([
                    html.Div(dcc.Graph(figure=tem_fig, responsive=True, style={"width": "100%", "height": "100%"}), 
                             style={"display": "flex", "width": "100%", "height": "100%"}),
                    html.Div(dcc.Graph(figure=bh_fig, responsive=True, style={"width": "100%", "height": "100%"}), 
                             style={"display": "flex", "width": "100%", "height": "100%"})
                ], style={"display": "flex", "flexDirection": "row", "height": "calc(100% - 10px)", "width": "100%","gap": "0px"})
                title = "TEM vs. Borehole Correlation"
                width_step = "950px" # Make window wider for side-by-side


                all_z = []
                # Add TEM elevations
                for idx in tem_ids:
                    row = df.loc[idx]
                    all_z.extend(row['elevation'] - row['bottom_depth'])
                    all_z.append(row['elevation'])

                # Add Borehole elevations
                for bh in bh_projections:
                    if bh['id'] in bh_ids:
                        all_z.append(bh['elev'])
                        all_z.append(bh['elev'] - max([l['Bottom'] for l in bh['layers']]))

                z_min = min(all_z) - 5 # 5m padding
                z_max = max(all_z) + 5

                # 2. Apply this exact range to both figures
                tem_fig.update_layout(yaxis=dict(range=[z_min, z_max], autorange=False))
                bh_fig.update_layout(yaxis=dict(range=[z_min, z_max], autorange=False))

            # Update Window list
            comp_id = combined_state["window_id"]
            windows = [w for w in windows if w["props"]["id"] != comp_id]
            windows.append(create_draggable_window(comp_id, title, content, width=width_step,height=height_step))
            
            return windows, combined_state

    # --- 2. HANDLE CLOSE BUTTON ---
    if "close-window" in trigger:
        try:
            prop_dict = json.loads(trigger.split(".")[0])
            closed_id = prop_dict.get("index")

            windows = [w for w in windows if w["props"]["id"] != closed_id]

            # Reset state if the comparison window was the one closed
            if combined_state.get("window_id") == closed_id:
                combined_state = {"window_id": None, "items": []}
        
            return windows, combined_state
        
        except Exception as e:
            print(f"Error closing window: {e}")

    return no_update, no_update

# --------------------- read and populate tiffs and pngs ---------------------
@app.callback(
    Output("dynamic-raster-layer-rows", "children"),
    Input("raster-registry-store", "data"),
)
def render_raster_layer_rows(rasters):
    rasters = rasters or []
    if not rasters:
        # Nothing loaded -> show nothing (or a hint)
        return no_update #html.Div("No rasters loaded", style={"fontSize": "11px", "color": "#666"})

    rows = []
    for r in rasters:
        # r example: {"id": "tiff_1", "kind": "tiff", "name": "myfile.tif", "default_opacity": 0.6}
        layer_id = r["id"]
        label = r.get("name", layer_id)
        default_op = r.get("default_opacity", 0.6)
        rows.append(layer_row(label, layer_id, checked=False, default_opacity=default_op))

    return rows


# --------------------- to give waiting signal when using tiffs for 1st time ---------------------
@app.callback(
    Output("raster-busy-overlay", "style"),
    Input("raster-busy-store", "data"),
    State("raster-busy-overlay", "style"),
)
def toggle_raster_loading(is_busy, style):
    style = style or {}
    style["display"] = "block" if is_busy else "none"
    return style

# --------------------- to give waiting signal when large profiles are made ---------------------
# @app.callback(
#     Output("profile-busy-overlay", "style"),
#     Input("profile-busy-store", "data"),
#     State("profile-busy-overlay", "style"),
# )
# def toggle_profile_busy(is_busy, style):
#     style = style or {}
#     style["display"] = "block" if is_busy else "none"
#     return style

@app.callback(
    Output("profile-busy-store", "data"),
    Output("profile-load-trigger", "data"),
    Input("line-final-store", "data"),
    Input("section-mode-store", "data"),
    Input("selected-line-index", "data"),
    State("profile-load-trigger", "data"),
    prevent_initial_call=True
)
def start_profile_loading(lines, mode, selected_idx, trig):
    trig = trig or 0
    if not lines:
        return {"busy": False, "since": 0}, trig
    return {"busy": True, "since": time.time()}, trig + 1

@app.callback(
    Output("profile-busy-overlay", "style"),
    Input("profile-busy-store", "data"),
    State("profile-busy-overlay", "style"),
)
def toggle_profile_busy(state, style):
    style = style or {}
    state = state or {"busy": False, "since": 0}

    if state.get("busy"):
        style["display"] = "block"
        return style

    # busy False: keep visible until MIN_MS has passed
    since = state.get("since", 0)
    elapsed_ms = (time.time() - since) * 1000.0

    style["display"] = "block" if elapsed_ms < 1000 else "none" # 700ms
    return style



# --------------------- Update map ---------------------
@app.callback(
    Output("something", "figure"),
    Output("raster-busy-store", "data" , allow_duplicate=True),
    
    Input("raster-load-trigger", "data"), 

    Input("layers-store", "data"),
    Input("opacity-store", "data"),
    Input("map-view-store", "data"),
    Input("line-final-store", "data"),
    Input("selected-line-index", "data"),
    Input("map-hover-marker-store", "data"),
    Input("raster-registry-store", "data"),     
    Input("points-color-map-store", "data"),
    Input("points-filter", "value"),
    State("points-attr", "value"),
    
    prevent_initial_call=True)

def update_map(_trigger, layers, opacity, view, lines,selected_idx, hover_pt,
               rasters,
            color_map, actual_filters, actual_attr, ):
    
    layers = layers or []
    opacity = opacity or {}
    # print("LINES", lines)

    rasters = rasters or []

    # ----- raster controls (dynamic TIFF/PNG rows) -----
    # Find which raster IDs are active
    active_rasters = [r for r in rasters if r.get("id") in layers]

    # For your CURRENT gis (single tiff + single png), pick first of each kind
    active_tiffs = [r for r in active_rasters if r.get("kind") == "tiff"]
    active_pngs  = [r for r in active_rasters if r.get("kind") == "png"]

    show_tiff = len(active_tiffs) > 0
    show_png  = len(active_pngs) > 0

    if show_tiff:
        gis.tiff_info = gis.get_tiff_info(active_tiffs[0]["path"])
    else:
        gis.tiff_info = None

    if show_png:
        gis.png_info = gis.get_png_info(active_pngs[0]["path"])
    else:
        gis.png_info = None

    # Use per-layer opacity if present; else default fallback
    tiff_layer_id = active_tiffs[0]["id"] if show_tiff else None
    png_layer_id  = active_pngs[0]["id"] if show_png else None

    tiff_op = opacity.get(tiff_layer_id, 0.6) if show_tiff else 0.6
    png_op  = opacity.get(png_layer_id, 0.6) if show_png else 0.6

    current_line = None
    if lines and len(lines) > 0:
        idx = selected_idx if selected_idx is not None else -1
        current_line = lines[idx]
    
    # Check if boreholes and points should be displayed
    is_points_visible = "points" in layers
    is_bh_visible = ("boreholes" in layers) and (bh_data is not None)
    
    if bh_data is not None:
        bh_projections = get_borehole_projections(current_line, bh_data, view, search_radius_m=Settings.radius)
    
    # if lines is not None:
        # print(f"Lines in store: {len(lines)}") 
        
    actual_attr = actual_attr or "date"
    actual_filters = actual_filters or []
    color_map = color_map or {}

    fig = gis.render(
        show_google="google" in layers,

        show_tiff=show_tiff,
        show_png=show_png,
        show_points=is_points_visible,
        google_op=opacity.get("google", 1),
        tiff_op=tiff_op,
        png_op=png_op,       
        view=view,
        final_line=lines,
        selected_idx=selected_idx,
        hover_pt=hover_pt,
        boreholes=bh_projections if is_bh_visible else None, # This now contains the Lon/Lat!
        show_boreholes=is_bh_visible,
        point_filters=actual_filters,
        point_attr=actual_attr,
        color_map=color_map,
        uirevision=f"{str(lines)}_{actual_attr}"
    )
    # print(f"DEBUG: Mapping {actual_attr}. Color Map Keys: {list(color_map.keys())[:5]}")

    if fig is None: return no_update

    if fig:
        # Just keep the camera stable
        fig.layout.uirevision = f"view_{actual_attr}"
        
        # Optional: ensure no leftover coloraxis if switching to Date
        if actual_attr == 'date':
            fig.layout.coloraxis = None
        
        # 2. FORCE empty shapes to kill the cyan preview
        fig.layout.shapes =  [] 
    
     # Force the uirevision to be unique to this attribute
    fig.layout.uirevision = f"{str(lines)}"
    return fig, False


# --------------------- Run ---------------------
if __name__ == "__main__":
    app.run(port=8050, debug=True)
    # app.run(port=8050)

# --------------------- Fix screen Resizing - STILL NEEDS TO ZOOM IN/OUT AFTER WINDOW RESIZING---------------------
app.clientside_callback(

    """
    function(id) {
        const el = document.getElementById(id);
        if (!el) return "";

        // Create the observer
        const ro = new ResizeObserver(entries => {
            for (let entry of entries) {
                // Find the internal leaflet map instance
                const mapEl = entry.target.querySelector('.leaflet-container');
                if (mapEl && mapEl._leaflet_map) {
                    mapEl._leaflet_map.invalidateSize();
                    
                    // Optional: nudge the map to redraw tiles
                    mapEl._leaflet_map.fire('move');
                }
            }
        });

        // Start watching the map container
        ro.observe(el);
        
        return "Observer Active";
    }
    """,
    Output('dummy-div-for-resize', 'children'),
    Input('map', 'id'),  # Assuming your dl.Map has id="map"
)


app.clientside_callback(
    """
    function(msg) {
        if(msg) {
            alert(msg);
        }
        return null;
    }
    """,
    Output("notification-store", "data"), # Clear it after showing
    Input("notification-store", "data")
)


app.clientside_callback(
    """
    function(values, ids) {
        // Event-based: set busy=True only when a raster checkbox flips OFF -> ON.
        // Keep internal memory of previous states so we detect the toggle event.

        if (!window._rasterPrevOn) window._rasterPrevOn = {};

        if (!values || !ids) {
            return window.dash_clientside.no_update;
        }

        for (let i = 0; i < ids.length; i++) {
            const id = ids[i];
            const v = values[i];

            if (!id || !id.layer) continue;

            const layer = id.layer;
            const isRaster = (typeof layer === "string") &&
                             (layer.startsWith("tiff_") || layer.startsWith("png_"));

            if (!isRaster) continue;

            const isOnNow = Array.isArray(v) && v.includes("on");
            const wasOn = !!window._rasterPrevOn[layer];

            // Update memory
            window._rasterPrevOn[layer] = isOnNow;

            // Trigger event: OFF -> ON
            if (!wasOn && isOnNow) {
                console.log("Raster turned ON:", layer, "=> set busy TRUE");
                return true;
            }
        }

        // Otherwise do nothing (do NOT return false; that would hide it)
        return window.dash_clientside.no_update;
    }
    """,
    Output("raster-busy-store", "data", allow_duplicate=True),
    Input({"type": "layer-check", "layer": ALL}, "value"),
    State({"type": "layer-check", "layer": ALL}, "id"),
    prevent_initial_call=True
)




