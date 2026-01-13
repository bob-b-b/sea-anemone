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

import pandas as pd
df_overview = pd.DataFrame(columns=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'])



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
            ])
          ], style={'padding': '10px', 'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}
      ),
      dcc.Location(id='url_button'),
      ]
, id='processing_buttons')

from Sections_plotting import *
df_data = TEMframe.from_usf_folder("C:/Users/au679476/OneDrive - Aarhus universitet/Documents/RGRPM_Ethiopia/102025_HRU_pilot/TEM_data/Day_3_15102025/Team_2_sTEM0053/USF_Files_fkr/")
#df_data = TEMframe.from_usf_folder()

m1 = Map(data=df_data.overview())
u1 = Upload(session_files=session_files)

m2 = ScatterMapRenderer(df_data)

panels = [u1, m2]
nodes = [node for panel in panels for node in panel.to_nodes()]+[dfl.Tab(id=f'tab-processing_buttons', children=[x]), dfl.Tab(id='tab-panel_list', children=[panel_list])]


html_header = html.H1('Sea Anemone', style={'width': '100%'})


test_layout = {'global': {'tabEnableClose': False}, 'borders': [{'type': 'border', 'selected': 0, 'size': 25, 'location': 'top', 'children': [{'type': 'Tab', 'id': '#16ae2179-565c-43e6-a343-bf9c33d810c7'}]}, {'type': 'border', 'size': 100, 'location': 'bottom', 'children': [{'type': 'tab', 'id': 'tab-processing_buttons', 'name': 'buttons'}, {'type': 'tab', 'id': 'tab-model_section', 'name': 'model section'}, {'type': 'tab', 'id': 'tab-table_overview', 'name': 'table overview'}]}], 'layout': {'type': 'column', 'id': '#862b2fc6-2ef4-4251-a485-e158ed2bf975', 'children': [{'type': 'tabset', 'id': '#328817bb-4e54-448e-887f-00356fda1ff9', 'weight': 45.20241768745649, 'children': [{'type': 'tab', 'id': 'tab-scatter_map', 'name': 'scatter_map'}], 'active': True}]}}

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
            model=test_layout,
            children=nodes,
            useStateForModel=False,        
        ),
    ], style={'marginTop': '60px'}),  # Push content below fixed header
    html.Div(id='output-click')
])

for panel in panels:
    panel.add_callbacks(app)

app.run(port=8050, debug=True)

# import os
# import base64
# import rasterio
# import matplotlib.pyplot as plt
# from rasterio.warp import calculate_default_transform, reproject, Resampling
# from rasterio.plot import reshape_as_image
# from PIL import Image
# import plotly.graph_objects as go
# import plotly.express as px
# from pyproj import Transformer
# import pandas as pd
# import numpy as np
# import math

# import matplotlib.cm as cm
# import matplotlib.colors as mcolors

# from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
# from dash.dependencies import Input, Output, State, ALL, MATCH
# from scipy.spatial import cKDTree
# from pyproj import Geod

# from basepanel import Panel, gear_maker, dcc
# from temframe import TEMframe

# from Sections_plotting import *
# from Map_external_layers import *
# # from Map_external_layers import parse_polyline_path




# # --------------------- Instantiate ---------------------
# renderer = ScatterMapRenderer(
#     dataframe=df,
#     settings=settings,
#     highlighted=1,
#     tiff_path=r"C:\Users\au679476\Downloads\test_tiff_Eth_32637.tiff",
#     png_path=r"C:\Users\au679476\Downloads\test_tiff_Eth_32637_wgs84_TEST_AS_PNG.png")

# renderer.id = 'something'
# app = Dash(__name__, suppress_callback_exceptions=True)
# app.title = "sea anemone"
# app.layout = renderer.initialize()


# # @app.callback(
# #     Output("dummy-output", "children"),
# #     Input(renderer.id, "relayoutData"),
# #     prevent_initial_call=True,)

# # def debug_print(relayout):
# #     print("\n\n==============================")
# #     print("RELAYOUT DATA RECEIVED:")
# #     print(relayout)
# #     print("==============================\n\n")
# #     return ""

# # --------------------- Layers Menu ---------------------
# # --------------------- Toggle the main layers panel ---------------------
# @app.callback(
#     Output("layers-panel", "style"),    
#     Input("layers-toggle", "n_clicks"),
#     State("layers-panel", "style"),
# )
# def toggle_layers_panel(n, style):
#     if not n:
#         return style
#     return {**style,"display": "block" if style["display"] == "none" else "none",}

# # --------------------- Toggle 3-dot menu per layer ---------------------
# @app.callback(
#     Output({"type": "layer-menu", "layer": MATCH}, "style"),
#     Input({"type": "layer-menu-btn", "layer": MATCH}, "n_clicks"),
#     State({"type": "layer-menu", "layer": MATCH}, "style"),)

# def toggle_layer_menu(n, style):
#     if not n:
#         return style
#     return {**style,"display": "block" if style["display"] == "none" else "none",}

# # --------------------- Collect active layers ---------------------
# @app.callback(
#     Output("layers-store", "data"),
#     Input({"type": "layer-check", "layer": ALL}, "value"),
#     State({"type": "layer-check", "layer": ALL}, "id"),
# )
# def collect_layers(values, ids):
#     return [i["layer"] for v, i in zip(values, ids) if v and "on" in v]

# # --------------------- Collect opacities ---------------------
# @app.callback(
#     Output("opacity-store", "data"),
#     Input({"type": "layer-opacity", "layer": ALL}, "value"),
#     State({"type": "layer-opacity", "layer": ALL}, "id"),)

# def collect_opacities(values, ids):    
#     return {i["layer"]: v for v, i in zip(values, ids)}

# # --------------------- Store zoom / center ---------------------
# @app.callback(
#     Output("map-view-store", "data"),   
#     Input(renderer.id, "relayoutData"),
#     State("map-view-store", "data"),
#     prevent_initial_call=True,)

# def update_map_view(relayout, view):

#     if not relayout:
#         return no_update

#     # store bbox
#     if "map._derived" in relayout and "coordinates" in relayout["map._derived"]:
#         coords = relayout["map._derived"]["coordinates"]

#         print("✔ Updated BBOX:", coords)

#         # keep previous center, zoom if available
#         center = relayout.get("map.center", (view or {}).get("center"))
#         zoom   = relayout.get("map.zoom",   (view or {}).get("zoom"))

#         return {
#             "bbox": coords,
#             "center": center,
#             "zoom": zoom,
#         }

#     return no_update

# # --------------------- Start line drawing ---------------------
# @app.callback(
#     Output("line-final-store", "data"),
#     Input(renderer.id, "relayoutData"), # this callback monitors ALL layout changes on the map.
#     State("map-view-store", "data"),
#     State("line-final-store", "data"), # We want to prevent overwriting when nothing happened    
#     prevent_initial_call=True)

# def on_draw(relayout, view, store):
#     if not relayout or "shapes" not in relayout:
#         return no_update

#     # BLOCK if map-view-store not updated yet
#     if not view or "bbox" not in view:
#         print("⛔ on_draw blocked — bbox not ready yet")
#         return no_update

#     shape = relayout["shapes"][-1]

#     # extract paper coordinates
#     x0, y0 = shape["x0"], shape["y0"]
#     x1, y1 = shape["x1"], shape["y1"]

#     # convert to geographic
#     p0 = paper_to_geo(x0, y0, view)
#     p1 = paper_to_geo(x1, y1,  view)

#     if p0 is None or p1 is None:
#         print("⛔ Conversion failed")
#         return no_update

#     print("✔ New line:", p0, p1)

#     # initialize list if needed
#     if store is None:
#         store = []

#     # append new line
#     store.append([p0, p1])

#     return  store  #(p0, p1)


# # --------------------- Toggle the profiles Panel ---------------------
# @app.callback(
#     Output("profiles-panel", "style"),
#     Input("profiles-toggle", "n_clicks"),
#     State("profiles-panel", "style"),
#     prevent_initial_call=True
# )
# def toggle_profiles_menu(n, current_style):
#     if n:
#         display = "block" if current_style.get("display") == "none" else "none"
#         current_style["display"] = display
#         return current_style
#     return current_style


# # --------------------- toggle the Section dropdown ---------------------
# @app.callback(
#     Output("section-panel", "style", allow_duplicate=True),
#     Input("section-toggle", "n_clicks"),
#     State("section-panel", "style"),
#     prevent_initial_call=True,
# )
# def toggle_section_panel(n, style):
#     if not n:
#         return style
#     new = style.copy()
#     new["display"] = "block" if style["display"] == "none" else "none"
#     return new

# # --------------------- selecting a section mode ---------------------
# @app.callback(
#     Output("section-mode-store", "data"),
#     Input({"type": "section-option", "mode": ALL}, "n_clicks"),
#     prevent_initial_call=True,
# )
# def select_section_mode(n_clicks):
#     ctx = callback_context
#     if not ctx.triggered:
#         return no_update

#     trigger_id = ctx.triggered[0]["prop_id"].split(".")[0]
#     mode = eval(trigger_id)["mode"]

#     print("MODE SELECTED:", mode)

#     return mode

# # --------------------- auto-close callback for sections ---------------------
# @app.callback(
#     Output("section-panel", "style", allow_duplicate=True),
#     Input({"type": "section-option", "mode": ALL}, "n_clicks"),
#     State("section-panel", "style"),
#     prevent_initial_call=True,
# )
# def close_section_panel(n_clicks, style):

#     # Prevent triggering when all are None or zero
#     if not any(n_clicks):
#         return no_update

#     new = style.copy()
#     new["display"] = "none"
#     print("Section panel closed.")
#     return new


# # --------------------- auto-close callback for layers ---------------------
# @app.callback(
#     Output("layers-panel", "style", allow_duplicate=True),
#     Input({"type": "layer-check", "layer": ALL}, "value"),   # checkboxes
#     Input({"type": "layer-opacity", "layer": ALL}, "value"),    # opacity sliders
#     Input({"type": "layer-menu-btn", "layer": ALL}, "n_clicks"),# 3-dot menus
#     State("layers-panel", "style"),
#     prevent_initial_call=True,
# )
# def auto_close_layers(layer_values, opacity_values, menu_clicks, style):

#     # Check for ANY triggered change:
#     changed = False

#     # Layer checkbox values (lists)
#     if layer_values and any(v is not None for v in layer_values):
#         changed = True

#     # Opacity slider values (floats)
#     if opacity_values and any(v is not None for v in opacity_values):
#         changed = True

#     # 3-dot menu clicks (ints)
#     if menu_clicks and any((x or 0) > 0 for x in menu_clicks):
#         changed = True

#     if not changed:
#         return no_update

#     # Close panel
#     new = style.copy()
#     new["display"] = "none"
#     print(">> Layers panel auto-closed")

#     return new

# # --------------------- live profile plot callback ---------------------
# @app.callback(
#     Output("profile-plot", "figure"),
#     Input("line-final-store", "data"),
#     Input("section-mode-store", "data"),
#     # Input("profile-selector-dropdown", "value"),
#     Input("selected-line-index", "data"),
#     prevent_initial_call=True
# )

# def update_section(lines, mode,selected_idx):
#     if not lines or len(lines) == 0:
#         return go.Figure()

#     # Always grab the last line drawn
#     # current_line = lines[-1]

#     # Use the selected index instead of [-1]
#     try:
#         current_line = lines[selected_idx]
#     except IndexError:
#         current_line = lines[-1]

#     p0, p1 = current_line

#     # 1) Sample along line
#     samples = sample_line_lonlat(p0, p1, 200)

#     # 2) Nearest-model interpolation (using 100m radius as per your code)
#     curves, sample_elevs, dists, idxs = interpolate_nearest(df, samples, radius=100)
    
#     # Filter out None values from the radius check   
#     valid_mask = [c is not None for c in curves]
#     valid_curves = [c for c in curves if c is not None]
#     valid_elevs = np.array(sample_elevs)[valid_mask]

#     if not valid_curves:
#         return no_update

#     y_depth = np.array(df["Depths"].iloc[0])[:-1] # Exclude math.inf
#     Z_interp = make_column_matrix(valid_curves)
#     x_interp = cumulative_distance_m(samples[:len(valid_curves)])

#     # --- Compute blocky section ---
#     Z_blocky, unique_idxs = collapse_by_station_only(idxs, df["resistivity"].values)
#     x_single = compute_station_positions(df, p0, p1)
    
#     # Sort for plotting
#     x_s_filtered = x_single[unique_idxs]
#     order = np.argsort(x_s_filtered)
#     x_s_final = x_s_filtered[order]
#     Z_b_final = Z_blocky[:, order]
#     station_elevs = df["elevation"].values[unique_idxs][order]

#     if mode == "interp":
#         return plot_section(x_interp, y_depth, Z_interp, elev=valid_elevs)
#     elif mode == "blocky":
#         return plot_column_section_blocky(x_s_final, y_depth, Z_b_final, elev=station_elevs)
#     elif mode == "combined":
#         return combine_sections(x_interp, y_depth, Z_interp, valid_elevs, x_s_final, Z_b_final, station_elevs)

#     return no_update
# # --------------------- live profile MULTI LINE plot callback ---------------------

# # @app.callback(
# #     Output("profile-plot", "figure"),
# #     Input("line-final-store", "data"),
# #     Input("section-mode-store", "data"),
# #     Input("selected-line-index", "data"),
# #     prevent_initial_call=True
# # )
# # def update_section(lines, mode, selected_idx):
# #     # 1. Safety check: If no lines exist, return an empty Figure object
# #     if not lines or len(lines) == 0:
# #         return go.Figure()

# #     # 2. Identify which line to plot
# #     try:
# #         # lines[selected_idx] is a list of [lon, lat] pairs
# #         current_line_coords = lines[selected_idx]
# #     except (IndexError, TypeError):
# #         current_line_coords = lines[-1]

# #     # 3. Generate the profile data (Sampling & Distance)
# #     # This uses the helper we discussed to handle multi-segment polylines
# #     try:
# #         all_x, all_vals = get_polyline_profile(current_line_coords, section_data=df)
        
# #         # Get depth array (assuming df has a constant depth structure per station)
# #         # We take all depths except the last one (often math.inf)
# #         y_depth = np.array(df["Depths"].iloc[0])[:-1] 
        
# #         # Determine elevations if available for the sampled points
# #         # For simplicity, we'll find the nearest station elevation for each sample
# #         # (This logic can be refined based on your interpolate_nearest function)
# #         valid_elevs = [sample_at_point(p[0], p[1], df, return_elev=True) for p in current_line_coords]
# #         # Note: If your sample_at_point doesn't support return_elev, set valid_elevs = None
# #     except Exception as e:
# #         print(f"Error during profile generation: {e}")
# #         return go.Figure()

# #     # 4. Routing based on the UI Mode
# #     # IMPORTANT: Each branch returns a go.Figure() object
    
# #     if mode == "interp":
# #         # Returns a Figure containing a go.Heatmap
# #         fig = plot_section(all_x, y_depth, all_vals, elev=None) # Start with None to test
        
# #     elif mode == "blocky":
# #         # If your blocky function returns a list of traces, wrap it here
# #         traces = create_blocky_polygons(all_x, y_depth, all_vals)
# #         if isinstance(traces, list):
# #             fig = go.Figure(data=traces)
# #         else:
# #             fig = traces # If it's already a figure

# #     elif mode == "combined":
# #         # Example of merging both into a single Figure object
# #         fig_interp = plot_section(all_x, y_depth, all_vals)
# #         traces_blocky = create_blocky_polygons(all_x, y_depth, all_vals)
        
# #         fig = go.Figure(data=fig_interp.data + (traces_blocky if isinstance(traces_blocky, list) else traces_blocky.data))
    
# #     else:
# #         # Default fallback
# #         fig = plot_section(all_x, y_depth, all_vals)

# #     # 5. Final Layout Polish
# #     # This ensures the figure is never empty and follows your app's theme
# #     fig.update_layout(
# #         template="plotly_white",
# #         height=450,
# #         margin=dict(l=50, r=20, t=40, b=50),
# #         yaxis=dict(autorange="reversed") # Standard for resistivity (surface at top)
# #     )

# #     return fig # RETURN THE OBJECT


# # --------------------- select profile dropdown and clear all or selected ---------------------
# @app.callback(
#     Output("line-final-store", "data", allow_duplicate=True),
#     Output("profile-list-container", "children"),
#     Output("selected-line-index", "data"),
#     Input("line-final-store", "data"),
#     Input("clear-selected-btn", "n_clicks"),
#     Input("clear-all-btn", "n_clicks"),
#     Input({"type": "view-line-btn", "index": ALL}, "n_clicks"), # Listen for any view button click
#     State({"type": "del-check", "index": ALL}, "value"),        # State of all checkboxes
#     State("selected-line-index", "data"),
#     prevent_initial_call=True
# )
# def master_line_controller(lines, clear_sel_n, clear_all_n, view_clicks, check_states, current_idx):
#     ctx = callback_context
#     if not ctx.triggered or not lines:
#         return [], [], 0, 0

#     trigger_id = ctx.triggered[0]["prop_id"]
    
#     # --- LOGIC: CLEAR ALL ---
#     if "clear-all-btn" in trigger_id:
#         return [], [], 0

#     # --- LOGIC: CLEAR SELECTED ---
#     if "clear-selected-btn" in trigger_id:
#         # check_states is a list of lists (e.g., [[], [1], []]). 
#         # We find indices where the inner list is not empty.
#         indices_to_remove = [i for i, val in enumerate(check_states) if val]
#         new_lines = [line for i, line in enumerate(lines) if i not in indices_to_remove]
#         new_active = max(0, len(new_lines) - 1)
#         return new_lines, no_update, new_active

#     # --- LOGIC: CHANGE VIEW (👁️) ---
#     new_active_idx = current_idx
#     if "view-line-btn" in trigger_id:
#         # Extract the index of the specific button clicked
#         prop_dict = eval(trigger_id.split(".")[0])
#         new_active_idx = prop_dict["index"]

#     # --- LOGIC: NEW LINE ADDED ---
#     if "line-final-store" in trigger_id:
#         new_active_idx = len(lines) - 1

#     # --- GENERATE THE UI ROWS ---
#     # This rebuilds the list so the "Active" one looks different
#     rows = []
#     for i in range(len(lines)):
#         is_active = (i == new_active_idx)
#         rows.append(html.Div(
#             style={
#                 "display": "flex", "alignItems": "center", "padding": "6px",
#                 "borderBottom": "1px solid #f0f0f0",
#                 "backgroundColor": "#e7f3ff" if is_active else "transparent"
#             },
#             children=[
#                 # 1. Label
#                 html.Span(f"Profile {i+1}", style={"flex": 1, "fontSize": "12px", "fontWeight": "bold" if is_active else "normal"}),
                
#                 # 2. View Button (👁️)
#                 html.Button(
#                     "👁️", 
#                     id={"type": "view-line-btn", "index": i},
#                     style={
#                         "border": "none", "background": "none", "cursor": "pointer", 
#                         "marginRight": "10px", "opacity": "1" if is_active else "0.4"
#                     }
#                 ),
                
#                 # 3. Delete Checkbox
#                 dcc.Checklist(
#                     id={"type": "del-check", "index": i},
#                     options=[{"label": "", "value": 1}],
#                     value=[],
#                     style={"display": "inline-block"}
#                 )
#             ]
#         ))

#     return no_update, rows, new_active_idx
# # --------------------- Update map ---------------------
# @app.callback(
#     Output("something", "figure"),
#     Input("layers-store", "data"),
#     Input("opacity-store", "data"),
#     Input("map-view-store", "data"),
#     Input("line-final-store", "data"),
#     Input("selected-line-index", "data"),
#     prevent_initial_call=True)

# def update_map(layers, opacity, view, lines,selected_idx):
#     layers = layers or []
#     opacity = opacity or {}
#     print("LINES", lines)

#     fig = renderer.render(
#         show_google="google" in layers,
#         show_tiff="tiff" in layers,
#         show_png="png" in layers,
#         show_points="points" in layers,
#         google_op=opacity.get("google", 1),
#         tiff_op=opacity.get("tiff", 0.6),
#         png_op=opacity.get("png", 0.6),
#         view=view,
#         final_line=lines,
#         selected_idx=selected_idx,
#     )
    
#     # fig.update_layout(shapes=[])
#     # 2. FORCE empty shapes to kill the cyan preview
#     fig.layout.shapes = [] 
    
#     # 3. Use uirevision to allow the map to "reset" its drawing layer 
#     # while keeping the zoom/pan state
#     # fig.update_layout(dragmode='drawopenpath',uirevision=str(lines))
#     fig.update_layout(dragmode='drawline',uirevision=str(lines))
    
#     return fig








# # @app.callback(
# #     Output("line-final-store", "data", allow_duplicate=True),
# #     Input(renderer.id, "relayoutData"),
# #     State("line-final-store", "data"),
# #     State("map-view-store", "data"), # Use this for the bbox conversion
# #     prevent_initial_call=True
# # )
# # def on_draw_finished(relayout_data, current_lines, view_data):
# #     if not relayout_data or "shapes" not in relayout_data:
# #         return no_update
        
# #     shape = relayout_data["shapes"][-1]
    
# #     # Handle both Path (multi-click) and x0/x1 (simple drag)
# #     if "path" in shape:
# #         path_str = shape.get("path", "")
# #         new_coords = parse_polyline_path(path_str, view=view_data)
# #     elif "x0" in shape:
# #         # Backward compatibility for simple drag lines
# #         p0 = paper_to_geo(shape["x0"], shape["y0"], view_data)
# #         p1 = paper_to_geo(shape["x1"], shape["y1"], view_data)
# #         new_coords = [p0, p1]
# #     else:
# #         return no_update
    
# #     if not new_coords or None in new_coords:
# #         return no_update
        
# #     lines = current_lines if current_lines else []
# #     lines.append(new_coords)
# #     return lines