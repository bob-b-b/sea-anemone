import sys, os
import base64
from tkinter import filedialog, Tk
import threading

fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)

import session
global sesh
sesh = None

# if len(sys.argv) == 2:
#     if sys.argv[1].endswith('session.json'):
#         sesh = session.Session.load(sys.argv[1])
#         sesh.load_dataframes()
#     else:
#         print('invalid path provided, must provide a session.json file for a project')

if sesh is None:
    sesh = session.Session()

from tempfile import NamedTemporaryFile
with NamedTemporaryFile() as f:
    tempdir = os.path.dirname(f.name)
session_tracker = os.path.join(tempdir, 'anemone_projects.txt')


from panels import *
from inversion_panels import *
import json
from dash import dcc
from dash import Dash, callback_context, ALL
from dash.exceptions import PreventUpdate
from dash import Input, Output, State, html, dcc, ctx
from dash_bootstrap_components import themes
import dash_bootstrap_components as dbc
from dash.dash import no_update
from flask import send_from_directory
import requests
import re
import shutil
import pandas as pd
import numpy as np

from temframe import TEMframe
from Map_external_layers import GIS_helpers
from GIS_profile_only import *
from Sections_plotting import *

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "Sea Anemone"

docs_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'build', 'html'))

@app.server.route('/help/<path:filename>')
def serve_help_docs(filename):
    return send_from_directory(docs_root, filename)


def _sanitize_filename(name: str, fallback: str = "dem.tif") -> str:
    if not name:
        return fallback
    base = os.path.basename(name)
    base = re.sub(r"[<>:\"/\\|?*]", "_", base)
    base = re.sub(r"[\x00-\x1f]", "_", base)
    base = base.strip(" .")
    if not base:
        return fallback
    root, ext = os.path.splitext(base)
    if not ext:
        ext = ".tif"
    max_root = 80
    if len(root) > max_root:
        root = root[:max_root]
    return f"{root}{ext}"


def build_data_summary():
    if sesh.data is None:
        return html.Div("No data loaded.")

    df = sesh.data
    if 'site_id' in df.columns:
        df_valid = df.loc[df['site_id'] != -1]
        n_sites = int(df_valid['site_id'].nunique())
    else:
        df_valid = df
        n_sites = int(len(df_valid))
    n_rows = int(len(df))

    summary_children = [
        html.Div(f"Loaded sites: {n_sites}")
    ]

    return html.Div(summary_children)


def _configure_tk_dpi_awareness():
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _sample_dem_at_points(lons, lats, dem_path):
    import rasterio
    from rasterio.warp import transform

    with rasterio.open(dem_path) as src:
        if src.crs and src.crs.to_epsg() != 4326:
            xs, ys = transform("EPSG:4326", src.crs, lons, lats)
            coords = list(zip(xs, ys))
        else:
            coords = list(zip(lons, lats))

        samples = list(src.sample(coords))
        dem_vals = np.array([s[0] if s is not None else np.nan for s in samples], dtype=float)
        if src.nodata is not None:
            dem_vals = np.where(dem_vals == src.nodata, np.nan, dem_vals)
    return dem_vals


def _export_kml_points(df, output_path):
    if df is None or df.empty:
        return "No data to export."
    required = {'longitude', 'latitude'}
    if not required.issubset(df.columns):
        return "Missing longitude/latitude columns."

    use_cols = ['longitude', 'latitude']
    name_col = 'site_id' if 'site_id' in df.columns else None
    elev_col = 'elevation' if 'elevation' in df.columns else None

    df_points = df.copy()
    df_points = df_points.dropna(subset=['longitude', 'latitude'])
    if df_points.empty:
        return "No valid lon/lat rows."

    def _safe_text(value):
        if value is None:
            return ""
        text = str(value)
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;")
                    .replace("'", "&apos;"))

    lines = [
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>",
        "<kml xmlns=\"http://www.opengis.net/kml/2.2\">",
        "  <Document>",
        "    <name>Sea Anemone Points</name>",
    ]

    for _, row in df_points.iterrows():
        lon = row['longitude']
        lat = row['latitude']
        try:
            lon_f = float(lon)
            lat_f = float(lat)
        except Exception:
            continue

        name = f"site_{row[name_col]}" if name_col else "site"
        name = _safe_text(name)

        desc_parts = []
        if name_col:
            desc_parts.append(f"site_id: {row[name_col]}")
        if elev_col:
            desc_parts.append(f"elevation: {row[elev_col]}")
        desc = _safe_text("; ".join(desc_parts))

        lines.extend([
            "    <Placemark>",
            f"      <name>{name}</name>",
            f"      <description>{desc}</description>",
            "      <Point>",
            f"        <coordinates>{lon_f},{lat_f},0</coordinates>",
            "      </Point>",
            "    </Placemark>",
        ])

    lines.extend([
        "  </Document>",
        "</kml>",
    ])

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(lines))

    return f"KML exported: {output_path}"


def build_gps_dem_summary():
    if sesh.data is None or not sesh.dem_path:
        return html.Div("GPS vs DEM: no DEM loaded.")

    df = sesh.data
    try:
        import rasterio
        from rasterio.warp import transform
    except Exception:
        return html.Div("DEM loaded. Install rasterio to compute GPS vs DEM.")

    if not all(col in df.columns for col in ['longitude', 'latitude', 'elevation']):
        return html.Div("GPS vs DEM: missing longitude/latitude/elevation columns.")

    if 'site_id' in df.columns:
        df_sites = df.loc[df['site_id'] != -1].drop_duplicates(subset=['site_id'])[['site_id', 'longitude', 'latitude', 'elevation']]
    else:
        df_sites = df[['longitude', 'latitude', 'elevation']].copy()

    lons = df_sites['longitude'].astype(float).to_numpy()
    lats = df_sites['latitude'].astype(float).to_numpy()
    gps = df_sites['elevation'].astype(float).to_numpy()
    valid_coords = np.isfinite(lons) & np.isfinite(lats) & np.isfinite(gps)
    if not valid_coords.any():
        return html.Div("GPS vs DEM: no valid lon/lat/elevation values.")

    df_sites = df_sites.loc[valid_coords].reset_index(drop=True)
    lons = lons[valid_coords]
    lats = lats[valid_coords]
    gps = gps[valid_coords]

    try:
        with rasterio.open(sesh.dem_path) as src:
            if src.crs and src.crs.to_epsg() != 4326:
                xs, ys = transform("EPSG:4326", src.crs, lons, lats)
                coords = list(zip(xs, ys))
            else:
                coords = list(zip(lons, lats))

            samples = list(src.sample(coords))
            dem_vals = np.array([s[0] if s is not None else np.nan for s in samples], dtype=float)
            if src.nodata is not None:
                dem_vals = np.where(dem_vals == src.nodata, np.nan, dem_vals)
    except Exception as exc:
        return html.Div(f"GPS vs DEM failed: {exc}")

    diff = gps - dem_vals
    valid = np.isfinite(diff)
    n_valid = int(valid.sum())
    if n_valid == 0:
        return html.Div("GPS vs DEM: no valid samples.")


    stats = {
        'mean': float(np.nanmean(diff)),
        'median': float(np.nanmedian(diff)),
        'std': float(np.nanstd(diff)),
        'min': float(np.nanmin(diff)),
        'max': float(np.nanmax(diff)),
    }

    try:
        import plotly.express as px
    except Exception:
        px = None

    plot_div = html.Div("Plot unavailable (plotly missing).")
    if px is not None:
        if 'site_id' in df_sites.columns:
            x_values = df_sites['site_id'].to_numpy()[valid]
            x_label = 'site_id'
        else:
            x_values = np.arange(len(diff))[valid]
            x_label = 'index'

        df_plot = pd.DataFrame({
            x_label: x_values,
            'gps_minus_dem': diff[valid]
        })

        fig = px.scatter(
            df_plot,
            x=x_label,
            y='gps_minus_dem',
            title='GPS - DEM by site',
        )
        fig.update_layout(
            height=260,
            margin={"l": 40, "r": 10, "t": 30, "b": 40},
            yaxis_title="GPS - DEM (m)",
            xaxis_title=x_label,
        )

        plot_div = dcc.Graph(figure=fig, config={"displayModeBar": False})

    return html.Div([
        html.Div([
            html.Div("GPS vs DEM (GPS - DEM, meters):"),
            html.Ul([
                html.Li(f"Samples: {n_valid}"),
                html.Li(f"Mean: {stats['mean']:.2f}"),
                html.Li(f"Median: {stats['median']:.2f}"),
                html.Li(f"Std: {stats['std']:.2f}"),
                html.Li(f"Min: {stats['min']:.2f}"),
                html.Li(f"Max: {stats['max']:.2f}"),
            ])
        ], style={'width': '45%'}),
        html.Div(plot_div, style={'width': '55%'})
    ], style={'display': 'flex', 'gap': '12px', 'alignItems': 'flex-start'})


if os.path.exists(session_tracker):
    with open(session_tracker, 'rt') as f:
        session_files = [x.strip() for x in f.readlines() if os.path.exists(x.strip())]
    session_files = list(set(session_files))

else:
    session_files = []

m1    = Map(data=sesh.overview)
dbdt1 = dbdtSounding(dataframe=sesh.data)
dbdt2 = dbdtSection(dataframe=sesh.data)
rhoa  = rhoaSounding(dataframe=sesh.data)

u1    = Upload(session_files=session_files)
mod1 = ModelGraph(   dataframe=sesh.models )
mod2 = ModelSection( dataframe=sesh.models )
Multi_inv = MultiInversion( dataframe=sesh.data )

# gis = GIS(dataframe =sesh.models)
profile = Profile(sesh.models)


Sing_inv = Single_site( dataframe=sesh.data, rho=10 )

hkr = HotKeyReminder()

panels = [u1, m1, dbdt1, dbdt2, mod1, mod2, Multi_inv, Sing_inv, rhoa, hkr, profile] #,gis
nodes = [node for panel in panels for node in panel.to_nodes()]#+[dfl.Tab(id=f'tab-profile-buttons', children=[profile_controls])] #dfl.Tab(id=f'tab-processing_buttons', children=[x]),


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
    dcc.Store(id="session-save-complete"),
    dcc.Store(id="starting-model", data={"rho": 10.0,"depth": np.cumsum(np.logspace(0, 1.3, 31)).tolist()}),
    dcc.Store(id='starting-model-selected',data=[]),
    dcc.Store(id='data-buffer',data={"length": 50, "start_site":0}),
    dcc.Store(id="dem-applied", data=False),
    dcc.Store(id="dem-downloaded", data=False),
    dcc.Store(id="dem-api-keys", data=[], storage_type="local"),
    dcc.Store(id="borehole-loaded", data=False),
    html.Div([dbc.Toast(
                    "⛔ Please Zoom or Pan in the map.",
                    id="zoom-toast",
                    header="Map Not Ready",
                    is_open=False,
                    dismissable=True,
                    duration=4000, # Disappears after 4 seconds
                    icon="danger",
                    style={"position": "fixed", "top": "50%", "left": "50%", "transform": "translate(-50%, -50%)", "width": 350, "zIndex": 9999,"textAlign": "center"},
                ),
            ], id="toast-container"),

    dcc.Store(id='global-colorbar-store', data={
            'resistivity': {'vmin': 1, 'vmax': 300, 'log': True},
            'DOI': {'vmin': 0, 'vmax': 500, 'log': False},
            'misfit': {'vmin': 0, 'vmax': 10, 'log': False},
            'number of gates': {'vmin': 0, 'vmax': 50, 'log': False},
            'date': {'vmin': 20240101, 'vmax': 20260101, 'log': False},
            'elevation': {'vmin': -100, 'vmax': 1000, 'log': False},
            'daytime': {'vmin': 0, 'vmax': 24, 'log': False},
            }), 
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
    html.Div(id='output-click'),
    dbc.Button(
        "?",
        id='help-fab',
        color='primary',
        style={
            'position': 'fixed',
            'right': '24px',
            'bottom': '24px',
            'width': '56px',
            'height': '56px',
            'borderRadius': '50%',
            'fontSize': '24px',
            'zIndex': 3000,
            'boxShadow': '0 6px 16px rgba(0,0,0,0.2)'
        }
    ),
    html.Div(id='help-window')
])

for panel in panels:
    panel.add_callbacks(app)


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
    Input("profile_plot_main", "clickData"),
    prevent_initial_call=True
)

# CALLBACK FOR PREPARING PROFILE MESSAGE
app.clientside_callback(
"""
function(selectedLineIdx, sectionMode, profileFig) {
    const triggered = dash_clientside.callback_context.triggered;
    if (!triggered || triggered.length === 0) return window.dash_clientside.no_update;

    const overlay = document.getElementById('profile-busy-overlay');
    if (!overlay) return window.dash_clientside.no_update;

    // --- Keep track of previous values in window scope ---
    window._lastSelectedLineIdx = window._lastSelectedLineIdx || null;
    window._lastSectionMode = window._lastSectionMode || null;

    const triggerId = triggered[0].prop_id;

    // --- SHOW overlay on real profile selection change ---
    if (triggerId.includes("selected-line-index.data")) {
        
        // DEBUG PRINTING
        console.log("--- Store Update ---");
        console.log("New Value:", selectedLineIdx);
        console.log("Last Value:", window._lastSelectedLineIdx);

        // 1. Only show if the value is a number AND different from the last one
        // This handles transitions like null -> 0 (first draw) and 0 -> 1 (navigation)
        const hasChanged = selectedLineIdx !== window._lastSelectedLineIdx;
        const isValid = selectedLineIdx !== null && selectedLineIdx !== undefined;

        if (hasChanged && isValid) {
            console.log("JS: Value changed. Showing overlay.");
            overlay.innerText = "Preparing Profile...";
            overlay.style.display = 'flex';
            overlay.style.position = 'fixed';
            overlay.style.top = '320px';
            overlay.style.left = '50%';
            overlay.style.width = '200px';
            overlay.style.marginLeft = '-100px';  // half the width to center
            overlay.style.textAlign = 'center';
            overlay.style.zIndex = '10000';
        } else {
            console.log("JS: Value is identical. Message stays hidden.");
        }

        // Always update the cache so the next zoom/pan comparison is accurate
        window._lastSelectedLineIdx = selectedLineIdx;
    }

    // --- SHOW overlay on section mode change ---
    if (triggerId.includes("section-mode-store.data")) {
        if (sectionMode !== window._lastSectionMode) {
            overlay.innerText = "Preparing Profile...";
            overlay.style.display = 'flex';
            overlay.style.position = 'fixed';
            overlay.style.top = '320px';
            overlay.style.left = '50%';
            overlay.style.width = '200px';
            overlay.style.marginLeft = '-100px';  // half the width to center
            overlay.style.textAlign = 'center';
            overlay.style.zIndex = '10000';
            console.log("JS: Section mode changed - showing overlay");
        }
        window._lastSectionMode = sectionMode;
    }

    // --- HIDE overlay after the profile figure updates ---
    if (triggerId.includes("profile_plot_main.figure")) {
        overlay.style.display = 'none';
        console.log("JS: Profile figure updated - hiding overlay");
    }

    return window.dash_clientside.no_update;
}
""",
Output("profile-busy-overlay", "title"),  #// dummy Output
Input("selected-line-index", "data"),
Input("section-mode-store", "data"),
Input("profile_plot_main", "figure"),
prevent_initial_call=True
)


@app.callback(
    [ 
        dbdt1.output, dbdt2.output, rhoa.output, mod1.output, mod2.output,
    ],
    [Input('map', 'relayoutData'), Input('map', 'selectedData')],
    prevent_initial_call=True
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
        # if 'shapes' in relayout_data:
        #     print("SHAPES IN HANDLE MAP INTERACTION LINE 582")
        #     m1.drawn_shapes = relayout_data['shapes']
        #     selected_sites = m1.get_selected_sites()
        # Handle shape deletion
        # elif any(key.startswith('shapes[') and key.endswith('].x0') for key in relayout_data.keys()):
        if any(key.startswith('shapes[') and key.endswith('].x0') for key in relayout_data.keys()):
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
        selected_sites = []
        for point in selected_data['points']:
            cd = point.get('customdata', None)
            if isinstance(cd, (list, tuple)) and len(cd) > 0:
                selected_sites.append(cd[0])

    # keep your sentinel if you rely on it elsewhere
    if selected_sites:
        selected_sites = list(set(selected_sites)) + [-1]
    
    # If no sites selected, don't update
    if not selected_sites:
        # print("NO SHAPES IN HANDLE MAP INTERACTION LINE 582")
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


# DRAGGABLE WINDOW FOR CTRL + ALT + LEFT CLICK
app.clientside_callback(
    """
    function(children) {
        if (!children) return window.dash_clientside.no_update;

        // Wait a tiny bit for the DOM to render the new window
        setTimeout(() => {
            const windows = document.getElementsByClassName("draggable-window");
            
            Array.from(windows).forEach(win => {
                const header = win.querySelector('.window-header');
                if (!header || header.dataset.listener === 'true') return;

                let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
                header.dataset.listener = 'true'; // Prevent double-attaching
                header.onmousedown = dragMouseDown;

                function dragMouseDown(e) {
                    e.preventDefault();
                    pos3 = e.clientX;
                    pos4 = e.clientY;
                    document.onmouseup = closeDragElement;
                    document.onmousemove = elementDrag;
                }

                function elementDrag(e) {
                    e.preventDefault();
                    pos1 = pos3 - e.clientX;
                    pos2 = pos4 - e.clientY;
                    pos3 = e.clientX;
                    pos4 = e.clientY;
                    win.style.top = (win.offsetTop - pos2) + "px";
                    win.style.left = (win.offsetLeft - pos1) + "px";
                }

                function closeDragElement() {
                    document.onmouseup = null;
                    document.onmousemove = null;
                }
            });
        }, 100);

        return window.dash_clientside.no_update;
    }
    """,
    Output("window-container", "className"), # Dummy output
    Input("window-container", "children"),   # Triggers whenever a window is added/removed
    prevent_initial_call=True
)

app.clientside_callback(
    """
        function(n_clicks) {
            if (n_clicks) {
                window.open(
                    '/help/index.html',
                    '_blank',
                    'width=1100,height=800,menubar=no,toolbar=no,location=no,status=no,scrollbars=yes,resizable=yes'
                );
            }
            return window.dash_clientside.no_update;
        }
    """,
    Output("help-window", "children"),
    Input("help-fab", "n_clicks"),
    prevent_initial_call=True
)

@app.callback(
    dbdt1.output, dbdt2.output, rhoa.output,
    Input("disableButton", "n_clicks"),
    Input("enableButton", "n_clicks"),
    State("tTEM", "selectedData"),
    State("sounding", "selectedData"),
    State("rhoa", "selectedData"),
    State('interpret_layout','color'),
    prevent_initial_call=True,
)
def show_value(n1, n2, ttem_selected, sounding_selected, rhoa_selected, interpret_layout_color):
    if interpret_layout_color == 'primary':
        raise PreventUpdate
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
    df_data['include'] = df_data['inuse_manual'].astype(bool, copy=True).fillna(df_data['inuse_auto'])
    dbdt1.dataframe = df_data[df_data['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    dbdt2.dataframe = df_data[df_data['site_id'].isin(dbdt2.dataframe['site_id'].unique())]
    rhoa.dataframe  = df_data[df_data['site_id'].isin(rhoa.dataframe['site_id'].unique())]
    return dbdt1.render(), dbdt2.render(), rhoa.render()

@app.callback(
    mod2.output, dbdt2.output, dbdt1.output, m1.output, mod1.output, rhoa.output,
    Input('data-buffer', 'data'),
    prevent_initial_call=True
)
def update_model_section_from_buffer(buffer_data):
    start  = buffer_data["start_site"]
    length = buffer_data["length"]

    # Update model section buffer
    mod2.buffer_start = start
    mod2.buffer_len   = length
    mod1.buffer_start = start
    mod1.buffer_len   = length
    

    # Update tTEM buffer
    dbdt2.buffer_start = start
    dbdt2.buffer_len   = length


    x_axis = dbdt2.settings.x_axis
    df = dbdt2.dataframe

    df_buf = dbdt2.dataframe.copy()
    if x_axis == "site_id":
        df_buf = df_buf[df_buf["site_id"] != -1]
    x_vals = np.sort(df_buf[x_axis].dropna().unique())

    x_slice = x_vals[start:start+length]

    buffer_sites = (
            df[
                (df[x_axis].isin(x_slice)) &
                (df["site_id"] != -1)
            ]["site_id"]
            .dropna()
            .unique()
        )


    if buffer_data.get("source") == "buffer_button":
        dbdt1.dataframe = sesh.data[sesh.data["site_id"].isin(buffer_sites)]
        rhoa.dataframe  = sesh.data[sesh.data["site_id"].isin(buffer_sites)]
    m1.buffer_sites = buffer_sites
    # rhoa.dataframe = sesh.data[sesh.data["site_id"].isin(buffer_sites)]
    # dbdt1.buffer_sites = buffer_sites
    if buffer_data.get("source") == "buffer_button":
        mod1.highlighted = None
        mod2.highlighted = None
        m1.highlighted = None
        dbdt2.highlighted = None
    return mod2.render(), dbdt2.render(), dbdt1.render(), m1.render(is_last_tab=False), mod1.render(), rhoa.render()

@app.callback(
    Output('data-buffer', 'data'),
    Input('beginning-buffer', 'n_clicks'),
    Input('next-buffer', 'n_clicks'),
    Input('prev-buffer', 'n_clicks'),
    State('data-buffer', 'data'),
    prevent_initial_call=True
)
def update_buffer(next_clicks, prev_clicks, beginning_clicks, buffer_data):
    if not ctx.triggered:
        raise PreventUpdate

    trigger = ctx.triggered_id

    length = buffer_data["length"]
    start  = buffer_data["start_site"]
    # Get total number of sites from models (safer than tTEM)
    if dbdt2.dataframe is None:
        raise PreventUpdate

    x_axis = dbdt2.settings.x_axis
    df = dbdt2.dataframe

    if x_axis == "site_id":
        df = df[df["site_id"] != -1]

    x_vals = np.sort(df[x_axis].dropna().unique())
    n_sites = len(x_vals)

    if trigger == "next-buffer":
        start += length
    elif trigger == "prev-buffer":
        start -= length
    elif trigger == "beginning-buffer":
        start = 0

    # Clamp safely
    start = max(0, min(start, max(0, n_sites - length)))

    buffer_data["start_site"] = start
    buffer_data['source'] = "buffer_button"
    return buffer_data

@app.callback(
    Output('data-buffer', 'data', allow_duplicate=True),
    Input('buffer-length-input', 'value'),
    State('data-buffer', 'data'),
    prevent_initial_call=True,
)
def update_buffer_length(new_length, buffer_data):
    if new_length is None or new_length <= 0:
        raise PreventUpdate

    buffer_data["length"] = int(new_length)

    # reset start if necessary to avoid overflow
    buffer_data["start_site"] = max(0, buffer_data["start_site"])

    return buffer_data

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
    prune_models_without_data()
    mod2.dataframe = sesh.models.copy() if sesh.models is not None else None
    mod1.dataframe = sesh.models.copy() if sesh.models is not None else None
    return mod2.render(), mod1.render()

@app.callback(
    Output("model_section", "figure", allow_duplicate=True),
    Input("interpret_layout", "n_clicks"),
    State("invert_layout", "color"),
    prevent_initial_call=True
)
def update_model_on_interpret(_, invert_color):
    # if invert_color != "primary":
        # raise PreventUpdate
    profile.dataframe = sesh.models.copy() if sesh.models is not None else None
    # mod1.dataframe = sesh.models.copy() if sesh.models is not None else None
    return mod2.render()


@app.callback(
    [Output('output-click', 'children', allow_duplicate=True),
    Output('session-save-complete', 'data', allow_duplicate=True),],
    Input('saveButton', 'n_clicks'),
    prevent_initial_call=True,
    allow_duplicate=True
)
def save_session(n1):
    if sesh.save_dir is None:
        _configure_tk_dpi_awareness()
        root = Tk()
        root.withdraw()  # Hide the root window
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()
        root.update()
        folder_path = filedialog.askdirectory(title="Select Save Directory", parent=root)
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
    kml_msg = None
    try:
        if sesh.data is not None:
            kml_path = os.path.join(sesh.save_dir, 'sites_with_elevation.kml')
            kml_msg = _export_kml_points(sesh.data, kml_path)
    except Exception as exc:
        kml_msg = f"KML export failed: {exc}"

    message = f"Session saved to {sesh.save_dir}"
    if kml_msg:
        message = f"{message}. {kml_msg}"

    return message, {"dir": sesh.save_dir}

@app.callback(
    Output("output-click", "children", allow_duplicate=True),
    m1.output, mod1.output, dbdt1.output, Multi_inv.output, mod2.output, dbdt2.output, rhoa.output,
    Output("data-buffer", "data", allow_duplicate=True),   # <-- ADD
    Input('highlight_prev', 'n_clicks'),
    Input('highlight_next', 'n_clicks'),
    State('invert_layout',  'color'),
    State('flex-layout', 'model'),
    State("data-buffer", "data"),                          # <-- ADD
    prevent_initial_call=True,
)
def highlight_change(n1, n2, invert_layout_color, model, buffer_data):
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    highlighted = m1.highlighted
    if trigger_id == 'highlight_prev':
        step = -1
    elif trigger_id == 'highlight_next':
        step = 1
    else:
        raise PreventUpdate

    if highlighted is None:
        raise PreventUpdate

    highlighted = highlighted + step

    # --- your existing updates ---
    df_data = sesh.data
    m1.highlighted = highlighted
    mod1.highlighted = highlighted
    mod2.highlighted = highlighted
    dbdt2.highlighted = highlighted
    dbdt1.dataframe = df_data[df_data['site_id'] == highlighted]
    rhoa.dataframe  = df_data[df_data['site_id'] == highlighted]

    # --- NEW: slide buffer only if highlight exits current buffer window ---
    new_buffer = no_update
    if buffer_data is not None and dbdt2.dataframe is not None:
        start  = buffer_data["start_site"]
        length = buffer_data["length"]

        x_axis = dbdt2.settings.x_axis
        df = dbdt2.dataframe

        # sorted axis positions
        # df_buf = dbdt2.dataframe.copy()
        if x_axis == "site_id":
            df_buf = df[df["site_id"] != -1]
        x_vals = np.sort(df[x_axis].dropna().unique())
        # x_vals = np.sort(df[x_axis].dropna().unique())

        # find index of highlighted site
        sel = df[df["site_id"] == highlighted]
        if not sel.empty:
            x_val = sel[x_axis].iloc[0]

            idx = np.where(x_vals == x_val)[0]
            if len(idx) > 0:
                idx = int(idx[0])

                # slide buffer when highlight exits window
                if idx-1 < start:
                    start = idx-5
                elif idx > start + length:
                    start = idx - length+4

                # clamp
                start = max(0, min(start, max(0, len(x_vals) - length)))

                buffer_data["start_site"] = start
                buffer_data["source"] = "site_nav"
                new_buffer = buffer_data

    return (
        ctx.triggered_id,
        m1.render(is_last_tab=False),
        mod1.render(),
        dbdt1.render(),
        Multi_inv.render(),
        mod2.render(),
        dbdt2.render(),
        rhoa.render(),
        new_buffer,   # <-- return updated buffer only when needed
    )


@app.callback(
    m1.output, mod1.output, dbdt1.output, mod2.output, dbdt2.output, rhoa.output,
    Input('model_section', 'clickData'),
    Input('tTEM', 'clickData'),
    Input('map', 'clickData'),
    State('invert_layout',  'color'),
    State('review_layout', 'color'),
    State('interpret_layout', 'color'),
    State('data-buffer', 'data'),
    prevent_initial_call=True
)
def cross_panel_click(model_click, ttem_click, map_click, invert_layout_color,review_layout_color, interpret_layout_color, buffer_data):
    if not ctx.triggered:
        raise PreventUpdate
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
    click_data = ctx.triggered[0]['value']
    site_id = None

    if not click_data or 'points' not in click_data:
        raise PreventUpdate
    if trigger_id == 'tTEM':
        x_value = click_data['points'][0]['x']
        site_id = dbdt2.dataframe.query(f'{dbdt2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'model_section':
        x_value = click_data['points'][0]['x']
        site_id = mod2.dataframe.query(f'{mod2.settings.x_axis} == @x_value')['site_id'].iloc[0]
    elif trigger_id == 'map':
        x_value,y_value = click_data['points'][0]['lon'],click_data['points'][0]['lat']
        all_dist = cdist(m1.dataframe.latitude, m1.dataframe.longitude, y_value+0.00000002, x_value+0.000000002)
        site_id = m1.dataframe.loc[np.argmin(all_dist), 'site_id']
        if m1.boreholes is not None:
            print('check the boreholes man!')

    df_data = sesh.data
    m1.highlighted    = site_id
    mod1.highlighted  = site_id
    mod2.highlighted  = site_id
    dbdt2.highlighted = site_id
    dbdt1.dataframe   = df_data[df_data['site_id'] == site_id]
    rhoa.dataframe    = df_data[df_data['site_id'] == site_id]
    return m1.render(is_last_tab=False), mod1.render(), dbdt1.render(), mod2.render(), dbdt2.render(), rhoa.render()

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


@app.callback(
    Output("inv-log-poll", "n_intervals"),
    Input("invert_all_button", "n_clicks"),
    prevent_initial_call=True,
)
def reset_polling(n):
    return 0

@app.callback(
    [Output('output-data-upload', 'children'),

     m1.output, dbdt1.output, dbdt2.output, rhoa.output,Multi_inv.output, Sing_inv.output,

     Output('output-data-summary', 'children', allow_duplicate=True),
     Output('upload-toast', 'is_open'),
     Output('upload-toast', 'children'),
    #  Output('gis', 'figure', allow_duplicate=True),
     Output('process_layout', 'disabled', allow_duplicate=True),
     Output('invert_layout', 'disabled', allow_duplicate=True),
     
     Output('process_layout', 'n_clicks', allow_duplicate=True),
     Output('dem-bbox-minlon', 'value', allow_duplicate=True),
     Output('dem-bbox-minlat', 'value', allow_duplicate=True),
     Output('dem-bbox-maxlon', 'value', allow_duplicate=True),
     Output('dem-bbox-maxlat', 'value', allow_duplicate=True),
     Output('dem-options-container', 'style', allow_duplicate=True),
     Output('borehole-options-container', 'style', allow_duplicate=True),
     
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
    warning_msg = None
    if sesh.save_dir is None:
        warning_msg = "No working directory selected. You can still explore data; choose Save to set one."
    if contents[0].startswith('data:application/x-zip'):
        try:
            sesh.data            = TEMframe.from_zip_content(contents[0])
        except Exception as e:
            return (html.Div("Upload failed."),no_update,no_update,no_update,no_update,no_update,no_update,build_data_summary(),True,f"Upload failed: Only one geometry is supported at a time",True,True,no_update,no_update,no_update,no_update,no_update,{'display': 'block'}, {'display': 'block'})
    sesh.data.history    = ['df_data = TEMframe.from_zip_content("uploaded_data_zip.txt")']
    sesh.site = sesh.overview
    sesh.data['include'] = sesh.data['inuse_manual'].astype(bool, copy=True).fillna(sesh.data['inuse_auto'])
    sesh.models          = None
    toast_tiff = ""
    if contents[0].startswith("data:application/tiff") or contents[0].startswith("data:image/tiff"):
        import base64
        content_type, content_string = contents[0].split(",")
        decoded = base64.b64decode(content_string)

        tiff_info = GIS_helpers.load_tiff_from_bytes(decoded)
        left, bottom, right, top = tiff_info["bounds"]

        m1.tiff_layer = tiff_info
        toast_tiff = "\n Loaded Tiff for Backgroundmap"
    # dbdt1.dataframe = sesh.data.copy()
    # buffer_sites = 
    # m1.dataframe    = sesh.overview
    m1.dataframe    = sesh.overview.copy()
    
    buffer_length = 50
    # unique_sites = np.sort(sesh.data['site_id'].unique())
    # unique_sites = np.sort(sesh.data.loc[sesh.data['site_id'] != -1, 'site_id'].unique())
    unique_sites = np.sort(sesh.site['site_id'].dropna().unique())
    unique_sites = unique_sites#[unique_sites != -1]
    initial_sites = unique_sites[:buffer_length]

    m1.buffer_sites = initial_sites.tolist()
    mod1.dataframe  = sesh.models
    mod1.buffer_sites = initial_sites.tolist()
    mod2.dataframe  = sesh.models

    profile.dataframe = sesh.models
    full_df = sesh.data.copy()

    buffered_df = full_df[full_df['site_id'].isin(initial_sites)].copy()

    dbdt1.dataframe = buffered_df
    dbdt2.dataframe = full_df          # keep full section view
    rhoa.dataframe  = buffered_df
    Multi_inv.dataframe = sesh.data.copy()
    Sing_inv.dataframe = sesh.data.copy()
    
    # t1.dataframe = TABLES['overview'].copy()
    new_process_clicks = no_update

    #return html.Div("File uploaded successfully."), False, False, new_process_clicks#, t1.render()
    summary = build_data_summary()
    if 'site_id' in sesh.data.columns:
        toast_count = int(sesh.data.loc[sesh.data['site_id'] != -1, 'site_id'].nunique())
    else:
        toast_count = int(len(sesh.data))
    toast_msg = f"Uploaded {toast_count} sites."+toast_tiff

    bbox_vals = (no_update, no_update, no_update, no_update)
    if 'longitude' in sesh.data.columns and 'latitude' in sesh.data.columns:
        min_lon = float(sesh.data['longitude'].min())
        max_lon = float(sesh.data['longitude'].max())
        min_lat = float(sesh.data['latitude'].min())
        max_lat = float(sesh.data['latitude'].max())
        pad = 0.01
        bbox_vals = (min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad)

    upload_msg = "File uploaded successfully."
    if warning_msg:
        upload_msg = f"{upload_msg} {warning_msg}"

    return html.Div(upload_msg), m1.render(), dbdt1.render(), dbdt2.render(), rhoa.render(), Multi_inv.render(), Sing_inv.render(), summary, True, toast_msg, False, False, new_process_clicks, *bbox_vals, {'display': 'block'}, {'display': 'block'}


@app.callback(
    Output('output-borehole-upload', 'children'),
    Output('borehole-loaded', 'data'),
    m1.output,
    Output('upload-toast', 'is_open', allow_duplicate=True),
    Output('upload-toast', 'children', allow_duplicate=True),
    Input('upload-borehole', 'contents'),
    State('upload-borehole', 'filename'),
    running=[(Output('upload-borehole', 'disabled'), True, False)],
    prevent_initial_call=True
)
def upload_borehole(contents, filename):
    if contents is None:
        raise PreventUpdate

    # Decode base64 content and write to temp file
    content_type, content_string = contents.split(',', 1)
    decoded = base64.b64decode(content_string)
    text = decoded.decode('utf-8', errors='replace')

    # Parse borehole data
    try:
        bh_data, rock_color_map = load_borehole_file(text, from_string=True)
    except Exception as e:
        return html.Div(f"Error parsing borehole file: {e}"), False, no_update, True, f"Borehole upload failed: {e}"

    if not bh_data:
        return html.Div("No boreholes found in file."), False, no_update, True, "No boreholes found."

    # Project UTM -> lat/lon
    boreholes = get_borehole_projections(bh_data)
    # print("BOREHOLES HERE",boreholes)

    # 1. Update Session
    sesh.borehole_list = boreholes
    sesh.rock_map = rock_color_map
    sesh.boreholes = boreholes_to_dataframe(bh_data)

    # Store on panels
    m1.boreholes = boreholes
    m1.rock_color_map = rock_color_map
    mod2.boreholes = boreholes
    mod2.rock_color_map = rock_color_map
    mod1.boreholes = boreholes
    mod1.rock_color_map = rock_color_map
    profile.boreholes = boreholes
    profile.rock_color_map = rock_color_map

    n_bh = len(bh_data)
    bh_ids = ', '.join(b['id'] for b in bh_data)
    msg = f"Loaded {n_bh} borehole(s): {bh_ids}"

    return html.Div(msg), True, m1.render(is_last_tab=False), True, f"Loaded {n_bh} borehole(s)"


@app.callback(
    Output('borehole-upload-container', 'style'),
    m1.output,
    Input('use-borehole', 'value'),
    prevent_initial_call=True
)
def toggle_borehole_upload(use_borehole):
    if use_borehole:
        return {'display': 'block', 'marginTop': '10px'}, no_update
    # Clear borehole data when unchecked
    m1.boreholes = None
    m1.rock_color_map = None
    mod2.boreholes = None
    mod2.rock_color_map = None
    mod1.boreholes = None
    mod1.rock_color_map = None
    return {'display': 'none', 'marginTop': '10px'}, m1.render()



@app.callback(
    Output('dem-options-container', 'style'),
    Output('borehole-options-container', 'style'),
    Input('upload-data', 'contents'),
    Input('url', 'hash'),
    prevent_initial_call=False
)
def toggle_dem_options(contents, url_hash):
    if sesh.data is None:
        return {'display': 'none'}, {'display': 'none'}
    return {'display': 'block'}, {'display': 'block'}

@app.callback(
    Output('dem-api-key-container', 'style'),
    Output('dem-resolution-container', 'style'),
    Output('dem-resolution', 'options'),
    Output('dem-resolution', 'value'),
    Input('dem-source', 'value'),
    State('dem-resolution', 'value'),
    prevent_initial_call=False
)
def toggle_dem_inputs(source, current_value):
    resolution_options_map = {
        'opentopo': [
            {'label': 'Global Copernicus GLO-30 (~30 m)', 'value': 'opentopo_cop30'},
            {'label': 'Global SRTMGL1 (~30 m)', 'value': 'opentopo_srtmgl1'},
            {'label': 'Global SRTMGL3 (~90 m)', 'value': 'opentopo_srtmgl3'},
            {'label': 'Global ALOS (~30 m)', 'value': 'opentopo_alos'},
        ],
        'etopo': [
            {'label': 'ETOPO2022 30 arc-second (surface, global)', 'value': 'etopo_30s'},
            {'label': 'ETOPO2022 60 arc-second (surface, global)', 'value': 'etopo_60s'},
        ],
    }

    options = resolution_options_map.get(source, [])
    valid_values = {opt['value'] for opt in options}
    default_value = options[0]['value'] if options else None
    value = current_value if current_value in valid_values else default_value

    if source == 'opentopo':
        return {'marginBottom': '8px'}, {'display': 'flex', 'gap': '10px'}, options, value
    return {'display': 'none'}, {'display': 'flex', 'gap': '10px'}, options, value

@app.callback(
    Output('output-dem-load', 'children'),
    Output('output-data-summary', 'children', allow_duplicate=True),
    Output('dem-applied', 'data'),
    Input('load-dem-vs-gps', 'n_clicks'),
    State('use-dem', 'value'),
    prevent_initial_call=True
)
def load_dem_vs_gps(n_clicks, use_dem):
    if not n_clicks:
        raise PreventUpdate
    if not use_dem:
        return html.Div("Enable 'Use DEM' first."), build_data_summary(), False
    if not sesh.dem_path or not os.path.exists(sesh.dem_path):
        return html.Div("No DEM found. Please download or upload a DEM first."), build_data_summary(), False

    stats = build_gps_dem_summary()
    replace_error = None
    try:
        df = sesh.data
        if df is not None:
            if 'elevation_gps' not in df.columns:
                df['elevation_gps'] = df['elevation']
            if 'site_id' in df.columns:
                df_sites = df.loc[df['site_id'] != -1].drop_duplicates(subset=['site_id'])[['site_id', 'longitude', 'latitude', 'elevation']]
                lons = df_sites['longitude'].astype(float).to_numpy()
                lats = df_sites['latitude'].astype(float).to_numpy()
                valid_coords = np.isfinite(lons) & np.isfinite(lats)
                df_sites = df_sites.loc[valid_coords].reset_index(drop=True)
                lons = lons[valid_coords]
                lats = lats[valid_coords]

                if len(df_sites) > 0:
                    dem_vals = _sample_dem_at_points(lons, lats, sesh.dem_path)
                    valid_dem = np.isfinite(dem_vals)
                    if valid_dem.any():
                        dem_map = pd.Series(dem_vals[valid_dem], index=df_sites.loc[valid_dem, 'site_id']).to_dict()
                        dem_series = df['site_id'].map(dem_map)
                        df.loc[dem_series.notna(), 'elevation'] = dem_series
            else:
                lons = df['longitude'].astype(float).to_numpy()
                lats = df['latitude'].astype(float).to_numpy()
                valid_coords = np.isfinite(lons) & np.isfinite(lats)
                if valid_coords.any():
                    dem_vals = _sample_dem_at_points(lons[valid_coords], lats[valid_coords], sesh.dem_path)
                    valid_dem = np.isfinite(dem_vals)
                    idx = df.index[valid_coords]
                    df.loc[idx[valid_dem], 'elevation'] = dem_vals[valid_dem]

            sesh.data = df
            if dbdt1.dataframe is not None and 'site_id' in df.columns:
                dbdt1.dataframe = df[df['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
            if dbdt2.dataframe is not None and 'site_id' in df.columns:
                dbdt2.dataframe = df[df['site_id'].isin(dbdt2.dataframe['site_id'].unique())]
    except Exception as exc:
        replace_error = exc

    message_children = [
        html.Div("DEM loaded. GPS vs DEM updated."),
        stats
    ]
    if replace_error is not None:
        message_children.append(html.Div(f"DEM elevation replace failed: {replace_error}"))

    dem_applied = replace_error is None
    return html.Div(message_children), build_data_summary(), dem_applied

@app.callback(
    Output('output-dem-load', 'children', allow_duplicate=True),
    Output('output-data-summary', 'children', allow_duplicate=True),
    Output('dem-applied', 'data', allow_duplicate=True),
    Input('restore-gps-elevation', 'n_clicks'),
    prevent_initial_call=True
)
def restore_gps_elevation(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    if sesh.data is None:
        return html.Div("No data loaded."), build_data_summary(), False
    df = sesh.data
    if 'elevation_gps' not in df.columns:
        return html.Div("No GPS elevation backup found."), build_data_summary(), False

    df['elevation'] = df['elevation_gps']
    sesh.data = df

    if dbdt1.dataframe is not None and 'site_id' in df.columns:
        dbdt1.dataframe = df[df['site_id'].isin(dbdt1.dataframe['site_id'].unique())]
    if dbdt2.dataframe is not None and 'site_id' in df.columns:
        dbdt2.dataframe = df[df['site_id'].isin(dbdt2.dataframe['site_id'].unique())]

    return html.Div("GPS elevation restored."), build_data_summary(), False

@app.callback(
    Output('restore-gps-elevation', 'disabled'),
    Input('dem-applied', 'data'),
    Input('use-dem', 'value'),
    prevent_initial_call=False
)
def toggle_restore_button(dem_applied, use_dem):
    return not bool(dem_applied and use_dem)

@app.callback(
    Output('output-dem-upload', 'children'),
    Output('output-data-summary', 'children', allow_duplicate=True),
    Output('dem-downloaded', 'data', allow_duplicate=True),
    Input('upload-dem', 'contents'),
    State('upload-dem', 'filename'),
    State('use-dem', 'value'),
    running=[(Output("upload-dem", "disabled"), True, False)],
    prevent_initial_call=True
)
def upload_dem(contents, filename, use_dem):
    if contents is None:
        raise PreventUpdate
    if not use_dem:
        raise PreventUpdate

    content_type, content_string = contents.split(',', 1)
    decoded = base64.b64decode(content_string)

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dem_dir = os.path.join(base_dir, 'cache', 'dem')
    os.makedirs(dem_dir, exist_ok=True)

    if not filename:
        filename = 'uploaded_dem.tif'

    safe_name = _sanitize_filename(filename, fallback="uploaded_dem.tif")
    dem_path = os.path.join(dem_dir, safe_name)

    with open(dem_path, 'wb') as f:
        f.write(decoded)

    sesh.dem_path = dem_path
    sesh.dem_name = safe_name

    return html.Div(f"DEM uploaded: {safe_name}"), build_data_summary(), False

@app.callback(
    Output('output-dem-download', 'children'),
    Output('output-data-summary', 'children', allow_duplicate=True),
    Output('dem-downloaded', 'data', allow_duplicate=True),
    Input('download-dem', 'n_clicks'),
    State('use-dem', 'value'),
    State('dem-source', 'value'),
    State('dem-api-key', 'value'),
    State('dem-bbox-minlon', 'value'),
    State('dem-bbox-minlat', 'value'),
    State('dem-bbox-maxlon', 'value'),
    State('dem-bbox-maxlat', 'value'),
    State('dem-resolution', 'value'),
    running=[(Output("download-dem", "disabled"), True, False)],
    prevent_initial_call=True
)
def download_dem(n_clicks, use_dem, source, api_key, min_lon, min_lat, max_lon, max_lat, resolution):
    if not n_clicks:
        raise PreventUpdate
    if not use_dem:
        return html.Div("Enable 'Use DEM' first."), build_data_summary(), False

    if None in (min_lon, min_lat, max_lon, max_lat):
        return html.Div("Please enter a complete bbox (min/max lon/lat)."), build_data_summary(), False
    if min_lon >= max_lon or min_lat >= max_lat:
        return html.Div("Invalid bbox: min values must be less than max values."), build_data_summary(), False

    download_url = None
    safe_name = None
    ot_params = None
    api_key_value = api_key

    if source == 'opentopo':
        demtype_map = {
            'opentopo_cop30': 'COP30',
            'opentopo_srtmgl1': 'SRTMGL1',
            'opentopo_srtmgl3': 'SRTMGL3',
            'opentopo_alos': 'ALOS',
        }
        demtype = demtype_map.get(resolution)
        if not demtype:
            return html.Div("Please choose a global DEM resolution."), build_data_summary(), False
        if not api_key_value:
            return html.Div("OpenTopography requires an API key. Paste it above."), build_data_summary(), False

        ot_params = {
            'demtype': demtype,
            'south': min_lat,
            'north': max_lat,
            'west': min_lon,
            'east': max_lon,
            'outputFormat': 'GTiff',
            'API_Key': api_key_value
        }
        download_url = 'https://portal.opentopography.org/API/globaldem'
        safe_name = _sanitize_filename(f"{demtype}_{min_lat:.6f}_{min_lon:.6f}_{max_lat:.6f}_{max_lon:.6f}.tif")
    elif source == 'etopo':
        etopo_map = {
            'etopo_30s': 'https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/30s/30s_surface_elev_gtif/ETOPO_2022_v1_30s_N90W180_surface.tif',
            'etopo_60s': 'https://www.ngdc.noaa.gov/mgg/global/relief/ETOPO2022/data/60s/60s_surface_elev_gtif/ETOPO_2022_v1_60s_N90W180_surface.tif',
        }
        download_url = etopo_map.get(resolution)
        if not download_url:
            return html.Div("Please choose an ETOPO resolution."), build_data_summary(), False

        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        dem_dir = os.path.join(base_dir, 'cache', 'dem')
        os.makedirs(dem_dir, exist_ok=True)

        global_name = _sanitize_filename(download_url.split('/')[-1])
        global_path = os.path.join(dem_dir, global_name)
        if not os.path.exists(global_path):
            try:
                with requests.get(download_url, stream=True, timeout=180) as r:
                    r.raise_for_status()
                    with open(global_path, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
            except Exception as exc:
                return html.Div(f"ETOPO download failed: {exc}"), build_data_summary(), False

        safe_name = _sanitize_filename(
            f"etopo_{resolution}_{min_lat:.6f}_{min_lon:.6f}_{max_lat:.6f}_{max_lon:.6f}.tif"
        )
        dem_path = os.path.join(dem_dir, safe_name)

        try:
            import rasterio
            from rasterio.windows import from_bounds

            with rasterio.open(global_path) as src:
                window = from_bounds(min_lon, min_lat, max_lon, max_lat, src.transform)
                window = window.round_offsets().round_lengths()
                data = src.read(1, window=window, boundless=True, fill_value=src.nodata)
                transform = src.window_transform(window)

                with rasterio.open(
                    dem_path,
                    'w',
                    driver='GTiff',
                    height=data.shape[0],
                    width=data.shape[1],
                    count=1,
                    dtype=data.dtype,
                    crs=src.crs,
                    transform=transform,
                    nodata=src.nodata,
                ) as dst:
                    dst.write(data, 1)
        except Exception as exc:
            return html.Div(f"ETOPO clip failed: {exc}"), build_data_summary(), False

        sesh.dem_path = dem_path
        sesh.dem_name = safe_name

        return html.Div(f"DEM downloaded: {safe_name}"), build_data_summary(), True
    else:
        return html.Div("Unknown DEM source."), build_data_summary(), False

    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    dem_dir = os.path.join(base_dir, 'cache', 'dem')
    os.makedirs(dem_dir, exist_ok=True)

    if not safe_name:
        safe_name = _sanitize_filename(download_url.split('?')[0])

    dem_path = os.path.join(dem_dir, safe_name)

    try:
        with requests.get(download_url, params=ot_params, stream=True, timeout=180) as r:
            r.raise_for_status()
            with open(dem_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        f.write(chunk)
    except Exception as exc:
        return html.Div(f"Download failed: {exc}"), build_data_summary(), False

    sesh.dem_path = dem_path
    sesh.dem_name = safe_name

    return html.Div(f"DEM downloaded: {safe_name}"), build_data_summary(), True

@app.callback(
    Output('save-dem', 'disabled'),
    Input('dem-downloaded', 'data'),
    Input('use-dem', 'value'),
    prevent_initial_call=False
)
def toggle_save_dem_button(dem_downloaded, use_dem):
    return not bool(dem_downloaded and use_dem)

@app.callback(
    Output('dem-downloaded', 'data', allow_duplicate=True),
    Input('use-dem', 'value'),
    prevent_initial_call=True
)
def reset_dem_downloaded(use_dem):
    if use_dem:
        raise PreventUpdate
    return False

@app.callback(
    Output('output-dem-save', 'children'),
    Input('save-dem', 'n_clicks'),
    State('dem-downloaded', 'data'),
    State('use-dem', 'value'),
    prevent_initial_call=True
)
def save_dem(n_clicks, dem_downloaded, use_dem):
    if not n_clicks:
        raise PreventUpdate
    if not use_dem:
        return html.Div("Enable 'Use DEM' first.")
    if not dem_downloaded:
        return html.Div("Please download a DEM first.")
    if not sesh.dem_path or not os.path.exists(sesh.dem_path):
        return html.Div("No DEM file found to save.")
    filename = sesh.dem_name or os.path.basename(sesh.dem_path)
    filename = os.path.splitext(filename)[0]

    _configure_tk_dpi_awareness()
    root = Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    root.lift()
    root.focus_force()
    root.update()
    save_path = filedialog.asksaveasfilename(
        title="Save DEM",
        initialfile=filename,
        parent=root
    )
    root.destroy()

    if not save_path:
        raise PreventUpdate

    try:
        save_path_effective = save_path
        valid_exts = {".tif", ".tiff", ".asc", ".bil", ".dem", ".xyz"}
        ext = os.path.splitext(save_path_effective)[1].lower()
        if ext not in valid_exts:
            save_path_effective = save_path_effective + ".tif"
        shutil.copy2(sesh.dem_path, save_path_effective)
    except Exception as exc:
        return html.Div(f"DEM save failed: {exc}")

    kml_msg = None
    kml_path = None
    try:
        if sesh.data is not None:
            kml_path = os.path.splitext(save_path_effective)[0] + ".kml"
            kml_msg = _export_kml_points(sesh.data, kml_path)
    except Exception as exc:
        kml_msg = f"KML export failed: {exc}"

    if kml_path and kml_msg and not kml_msg.startswith("KML export failed"):
        return html.Div([
            html.Div("DEM(tiff) and KML exported:"),
            html.Ul([
                html.Li(save_path_effective),
                html.Li(kml_path),
            ])
        ])
    if kml_msg:
        return html.Div([
            html.Div("DEM saved:"),
            html.Ul([html.Li(save_path_effective)]),
            html.Div(kml_msg)
        ])
    return html.Div([
        html.Div("DEM saved:"),
        html.Ul([html.Li(save_path_effective)])
    ])

@app.callback(
    Output('dem-api-key-list', 'children'),
    Output('dem-api-key-history', 'children'),
    Input('dem-api-keys', 'data'),
    prevent_initial_call=False
)
def sync_api_key_options(api_keys):
    keys = api_keys or []
    datalist_options = [html.Option(value=key) for key in keys]
    history_rows = []
    for key in keys:
        history_rows.append(
            html.Div(
                [
                    html.Button(
                        key,
                        id={'type': 'dem-api-key-select', 'index': key},
                        n_clicks=0,
                        style={
                            'border': 'none',
                            'background': 'transparent',
                            'padding': '0',
                            'textAlign': 'left',
                            'color': '#0d6efd',
                            'cursor': 'pointer',
                            'whiteSpace': 'nowrap'
                        }
                    ),
                    html.Button(
                        '❌',
                        id={'type': 'dem-api-key-delete', 'index': key},
                        n_clicks=0,
                        title='Remove from history',
                        style={
                            'border': 'none',
                            'background': 'transparent',
                            'cursor': 'pointer',
                            'padding': '0',
                            'marginLeft': '6px'
                        }
                    ),
                ],
                style={'display': 'flex', 'alignItems': 'center'}
            )
        )
    history_container = html.Div(
        history_rows,
        style={'display': 'flex', 'flexDirection': 'column', 'gap': '4px'}
    ) if history_rows else html.Div("No history yet.", style={'color': '#6c757d', 'fontSize': '12px'})
    return datalist_options, history_container

@app.callback(
    Output('dem-api-key-history-collapse', 'is_open'),
    Input('dem-api-key-history-toggle', 'n_clicks'),
    State('dem-api-key-history-collapse', 'is_open'),
    prevent_initial_call=True
)
def toggle_api_key_history(n_clicks, is_open):
    if not n_clicks:
        raise PreventUpdate
    return not is_open

@app.callback(
    Output('dem-api-key', 'value'),
    Output('dem-api-keys', 'data', allow_duplicate=True),
    Input({'type': 'dem-api-key-select', 'index': ALL}, 'n_clicks'),
    Input({'type': 'dem-api-key-delete', 'index': ALL}, 'n_clicks'),
    State('dem-api-keys', 'data'),
    prevent_initial_call=True
)
def handle_api_key_history(select_clicks, delete_clicks, api_keys):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    trigger = ctx.triggered_id
    keys = list(api_keys or [])

    if isinstance(trigger, dict) and trigger.get('type') == 'dem-api-key-select':
        key = trigger.get('index')
        return key, no_update

    if isinstance(trigger, dict) and trigger.get('type') == 'dem-api-key-delete':
        key = trigger.get('index')
        keys = [k for k in keys if k != key]
        return no_update, keys

    raise PreventUpdate

@app.callback(
    Output('dem-api-keys', 'data', allow_duplicate=True),
    Input('dem-downloaded', 'data'),
    State('dem-api-key', 'value'),
    State('dem-api-keys', 'data'),
    prevent_initial_call=True
)
def remember_api_key_on_download(dem_downloaded, api_key, api_keys):
    if not dem_downloaded:
        raise PreventUpdate
    if not api_key:
        raise PreventUpdate

    keys = list(api_keys or [])
    if api_key in keys:
        keys = [k for k in keys if k != api_key]
    keys.insert(0, api_key)
    return keys[:20]


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

def prune_models_without_data():
    """
    Remove models for sites that no longer have any active (in-use) *real* data.
    False/NaN are treated as inactive. Dummy rows (gate_id == -1) are ignored.
    """
    global sesh

    if sesh.data is None or sesh.models is None:
        return
    if 'site_id' not in sesh.data.columns or 'site_id' not in sesh.models.columns:
        return

    df = sesh.data

    # Only consider real gates (avoid the synthetic header rows at gate_id == -1)
    real_rows = pd.Series(True, index=df.index)
    if 'gate_id' in df.columns:
        real_rows &= df['gate_id'].fillna(-1).astype(int) >= 0
    if 'time' in df.columns:
        real_rows &= df['time'].notna()

    # Compute active flag (manual overrides auto; False/NaN inactive)
    if 'inuse_manual' in df.columns and 'inuse_auto' in df.columns:
        manual = df['inuse_manual']
        auto = df['inuse_auto']
        active_flag = manual.where(manual.notna(), auto).fillna(False).astype(bool)
    elif 'inuse_auto' in df.columns:
        active_flag = df['inuse_auto'].fillna(False).astype(bool)
    else:
        return

    # Final: active means "real row" AND "flagged active"
    active = real_rows & active_flag

    active_sites = df.loc[active, 'site_id'].dropna().unique()
    active_sites = [s for s in active_sites if s != -1]

    sesh.models = sesh.models[sesh.models['site_id'].isin(active_sites)].copy()



# --------------------- SECTION BUTTON ---------------------
@app.callback(
    Output("section-panel", "style"),
    Output("section-mode-store", "data"),
    Input("section-toggle", "n_clicks"),
    Input({"type": "section-option", "mode": ALL}, "n_clicks"),
    State("section-panel", "style"),
    State("section-mode-store", "data"),
    prevent_initial_call=True
)
def manage_section_mode(toggle_n, option_clicks, current_style, current_mode):
    ctx = callback_context
    if not ctx.triggered:
        return no_update, no_update

    trigger_id = ctx.triggered[0]["prop_id"]
    
    # Logic to show/hide the dropdown panel
    if "section-toggle" in trigger_id:
        is_visible = current_style.get("display") == "block"
        current_style["display"] = "none" if is_visible else "block"
        return current_style, no_update

    # Logic to handle picking a mode
    if "section-option" in trigger_id:
        # Extract the mode from the triggered ID dictionary
        triggered_dict = json.loads(trigger_id.split(".")[0])
        new_mode = triggered_dict["mode"]
        
        # Close the panel after selection
        current_style["display"] = "none"
        return current_style, new_mode

    return current_style, no_update


# --------------------- UPDATE PROFILE PLOT ---------------------
@app.callback(
    Output("profile_plot_main", "figure", allow_duplicate=True),
    Output("flex-layout", "action"),
    Input("map", "relayoutData"), 
    Input("section-mode-store", "data"),
    Input("selected-line-index", "data"),
    Input('global-colorbar-store', 'data'),
    State("map-view-store", "data"),
    prevent_initial_call=True
)
def update_profile_callback(relayout, mode, selected_idx, global_cbar_data, view):
    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    # Sync colorbars as before
    if global_cbar_data and 'resistivity' in global_cbar_data:
        res_config = global_cbar_data['resistivity']
        profile.settings.update_attributes(res_config)
    
    fig = profile.render(
        lines=m1.lines, 
        mode=mode, 
        selected_idx=selected_idx, 
        view=view
    )
    
    return fig, {"type": "select", "tabId": "tab-profile-plot-content_2"},# mod2.render()




@app.callback(
    Output('dem-upload-container', 'style'),
    Input('use-dem', 'value'),
    prevent_initial_call=False
)
def toggle_dem_upload(use_dem):
    if use_dem:
        return {'display': 'block', 'marginTop': '10px'}
    sesh.dem_path = None
    sesh.dem_name = None
    return {'display': 'none', 'marginTop': '10px'}

# @app.callback(Output('flex-layout', 'model',allow_duplicate=True), Input('flex-layout', 'model'), prevent_initial_call=True)
# def print_flex_layout_model(model):
#     print("Current flex-layout model:", model)
#     return no_update

@app.callback(
    [
        Output('flex-layout', 'model'),
        Output('upload_layout', 'color'),
        Output('process_layout', 'color'),
        Output('invert_layout', 'color'),
        Output('review_layout', 'color'),
        Output('interpret_layout', 'color'),
        Output('map', 'figure', allow_duplicate=True),
    ],
    [
        State('flex-layout', 'model'),
        State('selected-line-index', 'data'),
        Input("upload_layout", 'n_clicks'),
        Input("process_layout", 'n_clicks'),
        Input("invert_layout", 'n_clicks'),
        Input("review_layout", 'n_clicks'),
        Input("interpret_layout", 'n_clicks'),
    ],
    prevent_initial_call=True
)
def update_layout(model, active_idx,
                  load_clicks, process_clicks,
                  invert_clicks, review_clicks, interpret_clicks):

    ctx = callback_context
    if not ctx.triggered:
        raise PreventUpdate

    button_id = ctx.triggered[0]['prop_id'].split('.')[0]
    is_interpret = (button_id == 'interpret_layout')

    colors = {
        "upload_layout": 'secondary',
        "process_layout": 'secondary',
        "invert_layout": 'secondary',
        "review_layout": 'secondary',
        "interpret_layout": 'secondary'
    }
    colors[button_id] = 'primary'

    # 🔥 ONE render only
    map_fig = m1.render(
        current_idx=active_idx,
        is_last_tab=is_interpret
    )

    if button_id == "upload_layout":
        return layouts.upload, *colors.values(), map_fig

    elif button_id == "process_layout":
        return layouts.data, *colors.values(), map_fig

    elif button_id == "invert_layout":
        return layouts.invert, *colors.values(), map_fig

    elif button_id == "review_layout":
        return layouts.review, *colors.values(), map_fig

    elif button_id == "interpret_layout":
        return layouts.interpret, *colors.values(), map_fig


layout_output_list = [
        m1.output, dbdt1.output, dbdt2.output, rhoa.output, mod2.output,
        
        Output('flex-layout',    'model', allow_duplicate=True),

        Output('upload_layout',  'color',  allow_duplicate=True),
        Output('process_layout', 'color', allow_duplicate=True),
        Output('invert_layout',  'color', allow_duplicate=True),
        Output('review_layout',  'color', allow_duplicate=True), #Output('review_layout', 'disabled', allow_duplicate=True)
        Output('interpret_layout',  'color', allow_duplicate=True),
        
        Output('upload_layout',  'disabled',  allow_duplicate=True),
        Output('process_layout', 'disabled', allow_duplicate=True),
        Output('invert_layout',  'disabled', allow_duplicate=True),
        Output('review_layout',  'disabled', allow_duplicate=True), #Output
        Output('interpret_layout',  'disabled', allow_duplicate=True),
        Output("current-working-directory", "children", allow_duplicate=True),

        Output('use-borehole', 'value', allow_duplicate=True),
        Output('use-borehole', 'label', allow_duplicate=True),
        Output('borehole-options-container', 'style', allow_duplicate=True),


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
    if url_hash.startswith('#open_session'):
        root = Tk()
        root.withdraw()  # Hide the root window
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()
        root.update()
        folder_path = filedialog.askdirectory(title="Select Working Directory", parent=root)
        url_hash = '#load='+folder_path+'/'
    
    if url_hash.startswith('#change_working'):
        _configure_tk_dpi_awareness()
        root = Tk()
        root.withdraw()  # Hide the root window
        root.attributes('-topmost', True)
        root.lift()
        root.focus_force()
        root.update()
        folder_path = filedialog.askdirectory(title="Select Working Directory", parent=root)
        print(folder_path)
        root.destroy()  # Destroy the root window after selection
        if folder_path:
            sesh.save_dir = folder_path + '/' if not folder_path.endswith('/') else folder_path
            print(f'Working directory changed to: {sesh.save_dir}')
            res[-5] = sesh.save_dir

    if url_hash.startswith('#load'):
        folder = url_hash.split('=')[1].replace('%20', ' ').replace('%22', '')
        print(f'loading session from folder: {folder}')
        sesh = session.Session.from_folder(folder)
        # res[-2] = sesh.save_dir
        res[-5] = sesh.save_dir


        if hasattr(sesh, 'borehole_list') and sesh.borehole_list is not None:
            # Transfer data to the display models
            m1.boreholes = get_borehole_projections(sesh.borehole_list)
            mod1.boreholes = get_borehole_projections(sesh.borehole_list)
            mod2.boreholes = get_borehole_projections(sesh.borehole_list)
            profile.boreholes = get_borehole_projections(sesh.borehole_list)
            
            # Transfer the color map
            if hasattr(sesh, 'rock_map') and sesh.rock_map is not None:
                m1.rock_color_map = sesh.rock_map
                mod1.rock_color_map = sesh.rock_map
                mod2.rock_color_map = sesh.rock_map
                profile.rock_color_map = sesh.rock_map
            
            res[-4] = True  # use-borehole value
            res[-3] = html.Span(["Use Borehole Data ", 
                    html.B("(Loaded from Session)", style={'color': '#28a745'}),
                    html.Br(), # Adds a line break to keep it tidy
                    html.Small("Upload a new .bor file below to overwrite existing data.", style={'color': '#6c757d', 'fontStyle': 'italic', 'fontSize': '0.85rem'})])
            res[-2] = {'display': 'block', 'marginTop': '10px'} # container style
            
            res[0] = m1.render(is_last_tab=False)
        else:
            # If no boreholes, ensure UI reflects that
            res[-4] = False
            res[-3] = "Use Borehole Data (optional)"
            res[-2] = {'display': 'none'}

        if sesh.lines is not None:
            m1.lines = sesh.lines.copy()
            
        if sesh.data is not None:
            buffer_length = 50
            dbdt1.dataframe = sesh.data.copy()    
            # dbdt2.dataframe = sesh.data.copy()    
            m1.dataframe    = sesh.overview.copy()
            full_df = sesh.data.copy()
            unique_sites = np.sort(sesh.site['site_id'].dropna().unique())
            unique_sites = unique_sites[unique_sites != -1]
            initial_sites = unique_sites[:buffer_length]
            buffered_df = full_df[full_df['site_id'].isin(initial_sites)].copy()

            dbdt1.dataframe = buffered_df
            dbdt2.dataframe = full_df          # keep full section view
            rhoa.dataframe  = buffered_df
            m1.buffer_sites = initial_sites.tolist()
            dbdt2.buffer_sites = initial_sites.tolist()


            # rhoa.dataframe  = sesh.data.copy()    
            Multi_inv.dataframe = sesh.data.copy()
            Sing_inv.dataframe = sesh.data.copy()
            profile.dataframe= sesh.models.copy()  if sesh.models is not None else None
            res[0] = m1.render(is_last_tab=False)
            res[1] = dbdt1.render()
            res[2] = dbdt2.render()
            res[3] = rhoa.render()
        
        if sesh.models is not None:
            mod1.dataframe  = sesh.models.copy()
            mod2.dataframe  = sesh.models.copy()
            res[4] = mod2.render()

            res[6]   = 'secondary'
            res[7]   = 'secondary'
            res[8]   = 'secondary'
            res[9]   = 'success'
            res[10]  = 'secondary'
            res[11]  = False
            res[12]  = False
            res[13]  = False
            res[14]  = False
            res[15]  = False
        else:

            res[6]   = 'success'
            res[7]   = 'secondary'
            res[8]   = 'secondary'
            res[9]   = 'secondary'
            res[10]   = 'secondary'

            res[11]  = False
            res[12]  = False
            res[13]  = False
            res[14]  = True
            res[15]  = True
            
    res[-1] = ''
    return res




# # --------------------- #  MAP + PROFILE PLOT ---------------------
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
    
    profile.dataframe = sesh.models
    df_up_map, color_master_map, existing_attrs = preprocess_new_df(profile.dataframe)
    
    dbdt_df = sesh.data

    trigger = ctx.triggered[0]["prop_id"]
    windows = list(current_windows or [])
    # combined_state stores: {"window_id": str, "items": [[id, type], ...]}
    combined_state = combined_state or {"window_id": None, "items": []}
    width_step = "550px"
    height_step ="900px"
 

    all_bhs = m1.boreholes or []
    line_bhs = []

    if all_lines and selected_idx is not None:
        try:
            current_line = all_lines[selected_idx]
            if all_bhs:
                line_bhs = get_boreholes_on_line(current_line,all_bhs,search_radius_m=Settings.radius)
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
                fig = build_combined_borehole_figure([idx], all_bhs, m1.rock_color_map)
                title = f"Borehole Log: {idx}"
                content = html.Div([dcc.Graph(figure=fig, 
                                    style={"height": "750px"},
                                    config={'displayModeBar': False})]
                            , style={"height": "100%", "padding": "10px"})                    
            else:
                try:
                    row_data = None
                    if idx in df_up_map.index:
                        row_data = df_up_map.loc[idx] if idx in df_up_map.index else df_up_map.iloc[int(idx)]
                    else:
                        int_idx = int(idx)
                        if 0 <= int_idx < len(df_up_map):
                            row_data = df_up_map.iloc[int_idx]
                except (ValueError, TypeError):
                    row_data = None

                if row_data is not None:
                    fig_step = generate_res_step_graph(row_data, idx)            
                    fig_dbdt = generate_dbdt_graph(dbdt_df, idx)
                    
                    # 3. Create Tabs
                    tab_content = dcc.Tabs([
                        dcc.Tab(label='Res Step Plot', children=[
                            dcc.Graph(figure=fig_step, style={"height": "750px"})
                        ]),
                        dcc.Tab(label='Data (dB/dt)', children=[
                            dcc.Graph(figure=fig_dbdt, style={"height": "750px"})
                        ])
                    ], style={"height": "50px"})
                    
                    content = html.Div([tab_content], style={"height": "100%"})
                    title = f"TEM Sounding: {idx}"
                else:
                    return no_update, no_update
            
            windows.append(create_draggable_window(new_id, title, content, width=width_step, height=height_step))
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

            if len(bh_ids) == 0:
                # 1. Build the combined Resistivity plot
                fig_combined_step = build_combined_step_figure(df_up_map, tem_ids, use_elevation=True)
                
                # 2. Build the combined dB/dt plot
                fig_combined_dbdt = build_combined_dbdt_figure(sesh.data, tem_ids)
                
                # 3. Use Tabs for the content
                content = html.Div([
                    dcc.Tabs([
                        dcc.Tab(label=f'Combined Models ({len(tem_ids)})', children=[
                            dcc.Graph(figure=fig_combined_step, style={"height": "750px"})
                        ]),
                        dcc.Tab(label=f'Combined Data Fit', children=[
                            dcc.Graph(figure=fig_combined_dbdt, style={"height": "750px"})
                        ])
                    ])
                ], style={"height": "100%"})
                
                title = f"Comparison: {len(tem_ids)} Sites"
                width_step = "900px"

            # Scenario: Only Boreholes selected -> Side-by-Side Logs
            elif len(tem_ids) == 0:
                fig = build_combined_borehole_figure(bh_ids, all_bhs, m1.rock_color_map)
                content = dcc.Graph(figure=fig, style={"height": "100%"})
                title = f"Borehole Comparison ({len(bh_ids)})"

            else:
                # 1. Generate all three figures
                tem_fig = build_combined_step_figure(df_up_map, tem_ids, use_elevation=True)
                bh_fig = build_combined_borehole_figure(bh_ids, all_bhs, m1.rock_color_map)
                dbdt_fig = build_combined_dbdt_figure(sesh.data, tem_ids) # The new combined function
                
                # 2. Align Y-Axes for TEM and Borehole (Correlation Tab)
                all_z = []
                for idx in tem_ids:
                    row = df_up_map.loc[idx]
                    all_z.extend(row['elevation'] - row['bottom_depth'])
                    all_z.append(row['elevation'])
                for bh in all_bhs:
                    if bh['id'] in bh_ids:
                        all_z.append(bh['elev'])
                        all_z.append(bh['elev'] - max([l['Bottom'] for l in bh['layers']]))

                z_min, z_max = min(all_z) - 5, max(all_z) + 5
                tem_fig.update_layout(yaxis=dict(range=[z_min, z_max], autorange=False))
                bh_fig.update_layout(yaxis=dict(range=[z_min, z_max], autorange=False))

                # 3. Define the Correlation Content (Side-by-Side)
                correlation_content = html.Div([
                    html.Div(dcc.Graph(figure=tem_fig, responsive=True, style={"width": "100%", "height": "100%"}), 
                             style={"display": "flex", "width": "100%", "height": "100%"}),
                    html.Div(dcc.Graph(figure=bh_fig, responsive=True, style={"width": "100%", "height": "100%"}), 
                             style={"display": "flex", "width": "100%", "height": "100%"})
                ], style={"display": "flex", "flexDirection": "row", "height": "800px", "width": "100%","gap": "0px"})

                # 4. Wrap everything in Tabs
                content = html.Div([
                    dcc.Tabs([
                        dcc.Tab(label="Model Correlation (TEM vs BH)", children=[
                            correlation_content
                        ]),
                        dcc.Tab(label="Combined Data Fit (dB/dt)", children=[
                            dcc.Graph(figure=dbdt_fig, style={"height": "800px"})
                        ])
                    ])
                ], style={"height": "100%"})

                title = "TEM vs. Borehole Correlation"
                width_step = "900px" # Widened slightly for better side-by-side visibility

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

# # --------------------- #  hover on map from profile ---------------------
@app.callback(
    Output("map", "figure", allow_duplicate=True),
    Input("profile_plot_main", "hoverData"),
    State("selected-line-index", "data"),
    prevent_initial_call=True
)
def update_map_hover(hoverData, active_idx):
    if not hoverData or 'points' not in hoverData or not hoverData['points']:
        m1.hover_marker = None
        return m1.render(is_last_tab=True)

    try:
        point = hoverData['points'][0]
        custom = point.get('customdata')
        
        if custom is None:
            return no_update

        # Flatten nested customdata lists if they exist
        val = custom
        while isinstance(val, list) and len(val) > 0:
            val = val[0]
            
        if isinstance(val, list): return no_update

        # --- Case A: Site ID (Column Bar) ---
        is_site = False
        if sesh.models is not None and not sesh.models.empty:
            if val in sesh.models["site_id"].values:
                is_site = True

        if is_site:
            row = sesh.models[sesh.models["site_id"] == val]
            lat, lon = row.iloc[0]["latitude"], row.iloc[0]["longitude"]
        
        else:
            # --- Case B: Distance (Interpolated) ---
            if m1.lines is None or m1.lines.empty:
                return no_update
                
            unique_ids = sorted(m1.lines['line'].unique())
            idx = active_idx if (active_idx is not None and active_idx < len(unique_ids)) else -1
            
            target_id = unique_ids[idx]
            current_line_df = m1.lines[m1.lines['line'] == target_id]
            # Polyline expects [[lon, lat], [lon, lat]...]
            polyline = current_line_df[['longitude', 'latitude']].values.tolist()
            
            # Use your helper function
            geo_pos = get_geo_at_distance(polyline, float(val))
            
            # Since geo_pos is [lon, lat], extract by index
            lon, lat = geo_pos[0], geo_pos[1]

        # Update the class marker and render
        m1.hover_marker = {
            "latitude": lat,
            "longitude": lon}
        
        return m1.render(is_last_tab=True)

    except Exception as e:
        print(f"Hover Sync Error: {e}")
        return no_update


# --------------------- Warning for when map not zoomed in and view is None ---------------------
@app.callback(
    Output('zoom-toast', 'is_open'),
    Input('map', 'relayoutData'),
    prevent_initial_call=True
)
def show_zoom_warning(relayout_data):
    # If the user tries to draw a shape
    if relayout_data and 'shapes' in relayout_data:
        # Check if the coordinate system is missing
        if m1.view is None:
            return True            
    return False

# --------------------- MULTI LINE select profile dropdown and clear all or selected --------------------
@app.callback(
    # Output("profile-list-container", "children"),
    Output("selected-line-index", "data"),
    Output("map", "figure", allow_duplicate=True),
    Input("url", "hash"),
    Input("map", "relayoutData"),           
    Input("disableButton", "n_clicks"),
    Input("enableButton", "n_clicks"), 
    Input("highlight_next", "n_clicks"),
    Input("highlight_prev", "n_clicks"),     
    State("selected-line-index", "data"),
    State("profile_plot_main", "figure"), 
    State("interpret_layout", "color"),
    prevent_initial_call=True
)
def master_line_controller(url_hash,relayout, disable_n, enable_n, highlight_next_n, highlight_prev_n, current_idx, fig_data, interpret_color):
    if interpret_color != 'primary':
        raise PreventUpdate
    if not ctx.triggered:
        return no_update
    if url_hash and '#load' in url_hash:
        # from __main__ import sesh
        # If the session has lines, make sure m1 has them
        if sesh.lines is not None and not sesh.lines.empty:
            m1.lines = sesh.lines.copy()
            # print("Lines loaded into Controller via URL Trigger ")
        
    if m1.lines is None:
        m1.lines = pd.DataFrame(columns=['latitude', 'longitude', 'line'])

    unique_ids = sorted(m1.lines['line'].unique()) if not m1.lines.empty else []
    num_lines = len(unique_ids)
    if current_idx is None or current_idx >= num_lines:
        current_idx = num_lines - 1 if num_lines > 0 else 0

    trigger_id = ctx.triggered[0]["prop_id"]
    
    if "map.relayoutData" in trigger_id:
        if relayout and 'shapes' not in relayout:
            return no_update, no_update#, no_update, no_update, no_update#, False
        unique_ids = sorted(m1.lines['line'].unique())
        num_lines = len(unique_ids)
        current_idx = num_lines - 1

    # --- ACTION: PREVIOUS ---
    if "highlight_prev" in trigger_id:
        if num_lines == 0:
            raise PreventUpdate
        current_idx = max(0, current_idx - 1) 

    # --- ACTION: NEXT ---
    elif "highlight_next" in trigger_id:
        if num_lines == 0:
            raise PreventUpdate
        current_idx = min(num_lines - 1, current_idx + 1)
    elif "enableButton" in trigger_id:
        unique_ids = sorted(m1.lines['line'].unique())
        if current_idx >= len(unique_ids):
            return dbc.Alert("Error: Selected line index out of range.", color="danger")
            
        line_id = unique_ids[current_idx]
        # Filter the dataframe for just the coordinates of the current profile
        current_line_df = m1.lines[m1.lines['line'] == line_id]
        
        # Convert to list of dicts or whatever GIS_helpers expects
        current_coords = current_line_df.to_dict('records')

        target_dir = getattr(sesh, 'save_dir', None)
        if target_dir is None:
            target_dir = os.getcwd()
        # 4. Execute Save logic
        # Passing fig_data, coords, and the ID to your helper
        kmz_full_path, png_full_path = GIS_helpers.save_profile_data(
            fig_data, 
            current_coords, 
            line_id, 
            target_dir
        )
        
        kmz_name = os.path.basename(kmz_full_path)
        png_name = os.path.basename(png_full_path)
    # --- ACTION: CLEAR SELECTED ---
    elif "disableButton" in trigger_id:
        if num_lines == 0:
            raise PreventUpdate

        # line currently displayed on the map
        line_to_remove = unique_ids[current_idx]

        # remove it
        m1.lines = m1.lines[m1.lines["line"] != line_to_remove]
        sesh.lines = m1.lines.copy()

        # recompute ids
        unique_ids = sorted(m1.lines["line"].unique())
        num_profiles = len(unique_ids)


        if num_profiles == 0:
            current_idx = 0
            updated_map = m1.render(is_last_tab=True)
            updated_map.update_layout(shapes=[])
            return 0, updated_map
        else:
            # keep index valid
            current_idx = min(current_idx, num_profiles - 1)
            updated_map = m1.render(current_idx=current_idx, is_last_tab=True)

    num_profiles = len(unique_ids)
    
    prev_disabled = (current_idx <= 0) or (num_profiles == 0)
    next_disabled = (current_idx >= num_profiles - 1) or (num_profiles == 0)
    

    updated_map = m1.render(current_idx=current_idx,is_last_tab=True)
    updated_map.update_layout(shapes=[])

    rows = []
    for i, l_id in enumerate(unique_ids):
        is_active = (i == current_idx)
        rows.append(html.Div(
            style={
                "display": "flex", "alignItems": "center", "padding": "8px",
                "borderBottom": "1px solid #ddd",
                "backgroundColor": "#D1ECF1" if is_active else "transparent",
                "borderRadius": "4px", "marginBottom": "2px"
            },
            children=[
                html.Span(f"Profile {int(l_id)}", style={
                    "flex": 1, "fontSize": "13px", 
                    "fontWeight": "bold" if is_active else "normal"
                }),
            ]
        ))
    return current_idx, updated_map

import signal
@app.server.route("/shutdown", methods=["POST"])
def shutdown():
    print('closing app, saving data to zip...')
    sesh.save()    
    os.kill(os.getpid(), signal.SIGINT)  # Send a signal to the process to terminate


if __name__ == "__main__":
    try:
        app.run(port=8050)
    except Exception as e:
        print(f"Error running app: {e}")
    finally:
        print('closing app, saving data to zip...')
        sesh.save()
        os.kill(os.getpid(), signal.SIGINT)  # Send a signal to the process to terminate
#start msedge --app=http://127.0.0.1:8050/