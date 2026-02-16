import sys, os
import base64
from tkinter import filedialog, Tk


fpath = os.path.dirname(os.path.abspath(__file__))
if fpath not in sys.path:
    sys.path.append(fpath)

session_tracker = fpath+'/recent_projects.txt'

from panels import *

from dash import dcc
from dash import Dash, callback_context, ALL
from dash.exceptions import PreventUpdate
from dash_bootstrap_components import Button, ButtonGroup, themes
import dash_bootstrap_components as dbc
from dash.dash import no_update
from flask import send_from_directory

from temframe import TEMframe

external_stylesheets = [themes.BOOTSTRAP]
app = Dash(__name__, suppress_callback_exceptions=True, assets_folder='assets',  external_stylesheets=external_stylesheets)
app.title = "Sea Anemone"

docs_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'docs', 'build', 'html'))

@app.server.route('/help/<path:filename>')
def serve_help_docs(filename):
    return send_from_directory(docs_root, filename)


import os
import requests
import re
import shutil



import pandas as pd
import numpy as np
# df_overview = pd.DataFrame(columns=['date', 'daytime', 'latitude', 'longitude', 'elevation', 'utm_x', 'utm_y', 'distance'])

import session

global sesh
sesh = session.Session()


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

panels = [u1, m1, dbdt1, dbdt2, mod1, mod2, Inv_it, Sing_site, pyInt]

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
    dcc.Store(id="dem-applied", data=False),
    dcc.Store(id="dem-downloaded", data=False),
    dcc.Store(id="dem-api-keys", data=[], storage_type="local"),
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

    if kml_msg:
        return f"Session saved to {sesh.save_dir}. {kml_msg}"
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
     Output('output-data-summary', 'children', allow_duplicate=True),
     Output('upload-toast', 'is_open'),
     Output('upload-toast', 'children'),
     Output('map', 'figure', allow_duplicate=True),
     Output('sounding', 'figure', allow_duplicate=True),
     Output('tTEM', 'figure', allow_duplicate=True),
     Output('process_layout', 'disabled', allow_duplicate=True),
     Output('invert_layout', 'disabled', allow_duplicate=True),
     Output('process_layout', 'n_clicks', allow_duplicate=True),
     Output('dem-bbox-minlon', 'value', allow_duplicate=True),
     Output('dem-bbox-minlat', 'value', allow_duplicate=True),
     Output('dem-bbox-maxlon', 'value', allow_duplicate=True),
     Output('dem-bbox-maxlat', 'value', allow_duplicate=True),
     Output('dem-options-container', 'style', allow_duplicate=True),
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
    warning_msg = None
    if sesh.save_dir is None:
        warning_msg = "No working directory selected. You can still explore data; choose Save to set one."
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
    new_process_clicks = no_update

    summary = build_data_summary()
    if 'site_id' in sesh.data.columns:
        toast_count = int(sesh.data.loc[sesh.data['site_id'] != -1, 'site_id'].nunique())
    else:
        toast_count = int(len(sesh.data))
    toast_msg = f"Uploaded {toast_count} sites."

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

    return html.Div(upload_msg), summary, True, toast_msg, m1.render(), dbdt1.render(), dbdt2.render(), False, False, new_process_clicks, *bbox_vals, {'display': 'block'}#, t1.render()


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


@app.callback(
    Output('dem-options-container', 'style'),
    Input('upload-data', 'contents'),
    Input('url', 'hash'),
    prevent_initial_call=False
)
def toggle_dem_options(contents, url_hash):
    if sesh.data is None:
        return {'display': 'none'}
    return {'display': 'block'}


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
    Output('dem-bbox-minlon', 'value'),
    Output('dem-bbox-minlat', 'value'),
    Output('dem-bbox-maxlon', 'value'),
    Output('dem-bbox-maxlat', 'value'),
    Input('dem-bbox-from-data', 'n_clicks'),
    prevent_initial_call=True
)
def fill_dem_bbox_from_data(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    if sesh.data is None:
        return no_update, no_update, no_update, no_update
    if 'longitude' not in sesh.data.columns or 'latitude' not in sesh.data.columns:
        return no_update, no_update, no_update, no_update

    min_lon = float(sesh.data['longitude'].min())
    max_lon = float(sesh.data['longitude'].max())
    min_lat = float(sesh.data['latitude'].min())
    max_lat = float(sesh.data['latitude'].max())

    pad = 0.01
    return min_lon - pad, min_lat - pad, max_lon + pad, max_lat + pad

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


if __name__ == "__main__":
    try:
        is_frozen = getattr(sys, "frozen", False)
        app.run(port=8050, debug=not is_frozen, use_reloader=not is_frozen)
    except Exception as e:
        print(f"Error running app: {e}")
# finally:
#     print('closing app, saving data to zip...')
#     sesh.save()

#start msedge --app=http://127.0.0.1:8050/