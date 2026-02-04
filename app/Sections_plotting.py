import os
import base64
import rasterio
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
import re
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod

from basepanel import Panel, gear_maker, dcc, PanelSettings
from temframe import TEMframe

import io

num_layers = 28         # number of interpreted layers for TESTING
depth = 120       # number of depth samples per layer for TESTING

# # Sample dataframe for TESTING
# df = pd.DataFrame({
#     "latitude": [9.72, 9.70, 9.67, 9.69],
#     "longitude": [41.56, 41.58, 41.54, 41.55],
#     "value": [40.2, 50.8, 45.5, 47.9],
#     "Elevation": [1000.2, 1100.8, 1090.5, 1050.9],
#     "Resistivity" : [20, 38, 75, 1],
#     "ResModel":     [generate_res_model() for _ in range(4)],
#     "Depths":       [generate_depths() for _ in range(4)],
# })


# --------------------- Settings ---------------------
class Settings():
    color = "red"
    highlight_color = "yellow"
    zoom = 10
    png_crs = "EPSG:32637"
    bh_color = 'orange'
    geod = Geod(ellps="WGS84")
    res_min = 1
    res_max = 300
    norm = mcolors.LogNorm(vmin=res_min, vmax=res_max)
    cmap = cm.jet
    line_color="yellow"
    radius = 50 
    column_width = 60
    num_labels_colorbar = 4
    raster_cache_dir = r"C:\Users\au679476\Downloads\test_for_map_pngs_tiffs\raster_cache"

settings = Settings()



# ------------------------ COLORS ------------------------
def resist_to_rgba(res):
    """Convert resistivity value into Plotly rgba string using global cmap."""
    rgba = settings.cmap(settings.norm(res))  # returns (r,g,b,a) floats 0–1
    return f"rgba({rgba[0]*255:.0f},{rgba[1]*255:.0f},{rgba[2]*255:.0f},{rgba[3]:.2f})"

# ------------------------ COLORBAR HELPER ------------------------
def get_nice_log_labels(res_min, res_max, num_labels_colorbar):
# Get the raw log values
    raw_vals = np.logspace(np.log10(res_min), np.log10(res_max), num_labels_colorbar)

    nice_vals = []
    for v in raw_vals:
        if v == 0: 
            nice_vals.append(0)
            continue
        # Find the magnitude (power of 10)
        exponent = np.floor(np.log10(v))
        fraction = v / (10**exponent)
        
        # Round the fraction to a "nice" number: 1, 2, 3, 5, or 8
        if fraction < 1.5: nice_fraction = 1
        elif fraction < 2.5: nice_fraction = 2
        elif fraction < 4.0: nice_fraction = 3
        elif fraction < 6.5: nice_fraction = 5
        else: nice_fraction = 8
        
        nice_vals.append(nice_fraction * (10**exponent))

    return nice_vals

# ------------------------ COLORBAR  ------------------------
def create_geologic_colorbar(res_min, res_max, plot_height = 300):
    num_slices = 100
    # Logarithmic spacing for the colors to match your data distribution
    res_values = np.logspace(np.log10(res_min), np.log10(res_max), num_slices)
    label_values = get_nice_log_labels(res_min, res_max, Settings.num_labels_colorbar)
    slices = []
    
    for res in reversed(res_values): # Top to bottom
        color = resist_to_rgba(res)
        slices.append(html.Div(style={
            "backgroundColor": color,
            "flex": "1",
            "width": "40px"
        }))

    labels = []
    positions = np.linspace(0,1, Settings.num_labels_colorbar)
        
    for val, pos in zip(label_values, positions):
        percent = pos * 100
        labels.append(html.Div([
                # The tiny tick line
                html.Div(style={
                    "width": "8px", 
                    "height": "1px", 
                    "backgroundColor": "#333", 
                    "marginRight": "5px"
                }),
                # The text
                html.Span(f"{val:.1f}" ) #if val < 1 else f"{int(val)}
            ], style={
                "position": "absolute",
                "bottom": f"calc({percent}% - 7px)",
                "left": "-5px", # Shift left to make room for the tick
                "display": "flex",
                "alignItems": "center"
            }))

    return html.Div([
        # The Slanted Bar
        html.Div(slices, style={
            "display": "flex",
            "flexDirection": "column",
            "height": f"{plot_height}px",
            "border": "1px solid #333",
            "overflow": "hidden",
            "boxShadow": "2px 2px 5px rgba(0,0,0,0.2)"
                                }),
        # The Labels
        html.Div(labels, style={
            "position": "relative",
            "height": f"{plot_height}px",
            "width": "40px",
            "marginLeft": "12px",
            "fontSize": "12px",
            "fontWeight": "bold",
            "fontFamily": "sans-serif"
                                })
                ], 
                style={
                    "display": "flex", 
                    "alignItems": "center", 
                    "padding": "20px 10px",
                    "marginRight": "15px"
                    })


def create_geologic_colorbar_horizontal(res_min, res_max, bar_height=18):
    num_slices = 100

    # Log-spaced resistivity values
    res_values = np.logspace(np.log10(res_min), np.log10(res_max), num_slices)
    label_values = get_nice_log_labels(res_min, res_max, Settings.num_labels_colorbar)

    # --- Color slices (LEFT → RIGHT) ---
    slices = []
    for res in res_values:
        color = resist_to_rgba(res)
        slices.append(
            html.Div(
                style={
                    "backgroundColor": color,
                    "flex": "1",
                    "height": f"{bar_height}px",
                }
            )
        )

    # --- Labels + ticks ---
    labels = []
    positions = np.linspace(0, 1, len(label_values))

    # for val, pos in zip(label_values, positions):
    #     percent = pos * 100
    #     labels.append(
    #         html.Div(
    #             children=[
    #                 # Tick
    #                 html.Div(
    #                     style={
    #                         "width": "1px",
    #                         "height": "8px",
    #                         "backgroundColor": "#333",
    #                         "margin": "0 auto",
    #                     }
    #                 ),
    #                 # Text
    #                 html.Div(f"{val:.1f}",style={"marginBottom": "2px"}),
    #             ],
    #             style={
    #                 "position": "absolute",
    #                 "left": f"calc({percent}% - 100px)",
    #                 "transform": "translateX(-50%)",
    #                 # "top": "0px",
    #                 "textAlign": "center",
    #                 "fontSize": "11px",
    #                 "fontWeight": "bold",
    #                 "fontFamily": "sans-serif",
    #                 "whiteSpace": "nowrap",
    #             }
    #         )
    #     )

    for i, (val, pos) in enumerate(zip(label_values, positions)):
        # default: centered on its tick
        left = f"{pos * 100:.4f}%"
        transform = "translateX(-50%)"

        # edge cases: keep text inside the 80% bar
        if i == 0:
            left = "0%"
            transform = "translateX(0%)"
        elif i == len(label_values) - 1:
            left = "100%"
            transform = "translateX(-100%)"

        labels.append(
            html.Div(
                children=[
                    html.Div(style={
                        "width": "1px",
                        "height": "6px",
                        "background": "#333",
                        "margin": "0 auto",
                    }),
                    html.Div(f"{val:.1f}", style={"marginTop": "2px"})
                ],
                style={
                    "position": "absolute",
                    "left": left,
                    "transform": transform,
                    "textAlign": "center",
                    "fontSize": "11px",
                    "fontWeight": "bold",
                    "whiteSpace": "nowrap",
                }
            )
        )


    return html.Div(
        children=[
            # ---- BAR ----
            html.Div(
                children=slices,
                style={
                    "display": "flex",
                    # "flexDirection": "row",
                    "width": "100%",
                    "height": f"{bar_height}px",
                    "border": "1px solid #333",
                    "overflow": "hidden",
                    "boxShadow": "2px 2px 5px rgba(0,0,0,0.2)",
                },
            ),

            # ---- LABELS ----
            html.Div(
                children=labels,
                style={
                    "position": "relative",
                    "width": "100%",
                    "height": "30px",
                    "marginTop": "4px",
                    "padding": "0",          # important
                    "boxSizing": "border-box"
                },
            ),
        ],
        style={
            "width": "100%",
            # "padding": "6px 12px",
            # "boxSizing": "border-box",
        },
    )


# ------------------------ # DEPTH MODEL GENERATOR for TESTING # ------------------------
def generate_depths():
    depths = list(np.logspace(0, np.log10(depth), num_layers))  # example: 0 → 50 meters
    depths.append(math.inf)  # last depth → infinite
    return depths  # length = 20

# ------------------------# RESISTIVITY MODEL for TESTING # ------------------------
def generate_res_model():
    return np.random.uniform(settings.res_min, settings.res_max, size=num_layers)

# ----------- BOREHOLES ----------------

def load_borehole_file(file_path):
    with open(file_path, 'r') as f:
        content = f.read()

    blocks = re.split(r'(?=BoreholeNo=)', content)
    blocks = [b.strip() for b in blocks if "BoreholeNo=" in b]
    
    all_boreholes = []

    for i, block in enumerate(blocks):
        def get_meta(field, text):
            match = re.search(f"{field}=(.*)", text)
            return match.group(1).strip() if match else None

        try:
            bh_id = get_meta("BoreholeNo", block)
            elev = float(get_meta("Elevation", block))
            
            bh_metadata = {
                "bh_index": i,
                "id": bh_id,
                "x": float(get_meta("XUTM", block)),
                "y": float(get_meta("YUTM", block)),
                "elevation": elev,
            }

            table_start_index = block.find("Top")
            if table_start_index == -1: continue

            # Get the lines of the table
            table_lines = block[table_start_index:].strip().split('\n')
            if len(table_lines) < 2: continue # Only header, no data

            # --- PARSING LOGIC ---
            data_rows = []
            # Start from index 1 to skip the header "Top Bottom..."
            for line in table_lines[1:]:
                # This Regex finds numbers and quoted strings or single words
                # It handles: 0.00  16.00  "Some Description"  SS2
                parts = re.findall(r'(".*?"|\S+)', line)
                
                if len(parts) >= 2:
                    # Pad parts if RockType or Description are missing
                    while len(parts) < 4:
                        parts.append("")
                    
                    data_rows.append({
                        "Top": float(parts[0]),
                        "Bottom": float(parts[1]),
                        "LayerDescription": parts[2].replace('"', ''), # Remove quotes
                        "RockType": parts[3]
                    })

            df_layers = pd.DataFrame(data_rows)

            # Clean up the data
            if not df_layers.empty:
                df_layers['RockType'] = df_layers['RockType'].replace('Nan', 'Unspecified')
                df_layers['RockType'] = df_layers['RockType'].replace('', 'Unspecified')
                
                bh_metadata["layers"] = df_layers.to_dict('records')
                all_boreholes.append(bh_metadata)
                # print(f"✔️ Loaded Borehole: {bh_id} ({len(bh_metadata['layers'])} layers)")

        except Exception as e:
            print(f"❌ Error parsing borehole {bh_id if 'bh_id' in locals() else 'unknown'}: {e}")

    # --- Global Color Map ---
    all_rock_types = set()
    for bh in all_boreholes:
        for layer in bh['layers']:
            rt = layer['LayerDescription']
            if rt: all_rock_types.add(rt)
    
    sorted_rocks = sorted(list(all_rock_types))
    cmap = plt.get_cmap('tab20b')
    rock_color_map = {}
    if sorted_rocks:
        colors = np.linspace(0.1, 0.9, len(sorted_rocks))
        for i, rock in enumerate(sorted_rocks):
            rock_color_map[rock] = mcolors.to_hex(cmap(colors[i]))

    # print(f"🚀 TOTAL LOADED: {len(all_boreholes)} boreholes.")
    return all_boreholes, rock_color_map

def get_borehole_projections(line_coords, boreholes, view, search_radius_m=settings.radius):
    """
    If line_coords exists: Returns boreholes within radius + projection data.
    If line_coords is None: Returns all boreholes with map coordinates only.
    """
    if isinstance(boreholes, dict):
        boreholes = [boreholes]
    
    if isinstance(boreholes, list) and len(boreholes) > 0 and isinstance(boreholes[0], list):
        boreholes = boreholes[0]
    
    # Check if we have a valid line to project onto
    has_line = line_coords is not None and len(line_coords) >= 2
    projections = []
    transformer = Transformer.from_crs(settings.png_crs, "EPSG:4326", always_xy=True)
    
    for bh in boreholes:    
        # 1. Always convert UTM -> Paper -> Geo for the Map
        lon, lat = transformer.transform(bh['x'], bh['y'])
        s_pt = (lon, lat)

        if s_pt is None: continue
                # Create the base data that the map needs
        bh_entry = {
                    "id": bh['id'],
                    "map_lon": s_pt[0], 
                    "map_lat": s_pt[1],
                    "elev": bh['elevation'],
                    "layers": bh['layers'],
                    "geo_pt": s_pt,
                    "dist_x": 0,       # Default
                    "is_on_section": False # Flag to tell the section plotter to ignore it
                    }
        
        if has_line:
            # 2. If line exists, do the projection math
            dist_along, dist_from = project_station_onto_polyline(s_pt, line_coords)
            
            # Only add to list if it's within the buffer
            if dist_from <= search_radius_m:
                projections.append({
                    "id": bh['id'],
                    "dist_x": dist_along,
                    "map_lon": lon,# s_pt[0], 
                    "map_lat": lat, #s_pt[1],
                    "elev": bh['elevation'],
                    "layers": bh['layers'],
                    "geo_pt": s_pt,
                    "is_on_section": True # Flag to know it's on the section
                })
        else:
            # 3. No line drawn: just return coordinates so they show on map
            projections.append({
                "id": bh['id'],
                "dist_x": 0, # No distance along line available
                "map_lon": lon,# s_pt[0], 
                "map_lat": lat, #s_pt[1],
                "elev": bh['elevation'],
                "layers": bh['layers'],
                "geo_pt": s_pt,
                "is_on_section": False
            })

    # 3. ALWAYS add the borehole to the list so it shows on the map
        projections.append(bh_entry)

    return projections

def add_boreholes_to_fig(fig, bh_projections,rock_color_map):
    added_to_legend = set()
    for bh in bh_projections:

        # ONLY draw the borehole on the section if it's near the line
        if not bh.get("is_on_section", False):
            continue
        
        bh_id = bh.get('id')
        
        for layer in bh['layers']:

            z_bottom = bh['elev'] - float(layer['Top'])
            z_top = bh['elev'] - float(layer['Bottom']) 

            x_box = [bh['dist_x'] - settings.column_width/2, bh['dist_x'] + settings.column_width/2, 
                     bh['dist_x'] + settings.column_width/2, bh['dist_x'] - settings.column_width/2, bh['dist_x'] - settings.column_width/2]
            y_box = [z_top, z_top, z_bottom, z_bottom, z_top]


            rock = layer.get('LayerDescription', '').strip()
            # Get color from our global map
            color = rock_color_map.get(rock)
            
            # Check if we should show this rock type in the legend
            show_in_legend = False
            if rock not in added_to_legend:
                # show_in_legend = True
                show_in_legend = False
                added_to_legend.add(rock)

            # Draw each layer as a thicker vertical line or rectangle
            fig.add_trace(go.Scatter(
                x=x_box, y=y_box,
                fill="toself",
                fillcolor=color,
                mode='lines',
                line=dict(width=0.5,color='black'),
                # --- LEGEND SETTINGS ---
                name=rock,
                showlegend=show_in_legend,
                legendgroup=rock, 
                customdata=[[bh_id, bh['dist_x'] , "borehole"]] * len(x_box),
                # --- HOVER SETTINGS ---
                hovertext=f"{layer.get('LayerDescription', '')}",
                hoveron='points',
            ))
            
            # fig.update_layout(hovermode='closest', # Shows only the data point your mouse is touching
            #         )
        # # Add a label at the top
        fig.add_annotation(
            x=bh['dist_x'], 
            y=bh['elev'],
            text=f"<b>{bh['id']}</b>", # Bold text
            showarrow=False,           # Removing arrow for a cleaner look
            yshift=10,                 # Offset it slightly upwards from the top
            xanchor='center',          # Horizontal center
            yanchor='bottom',          # Anchors the bottom of text to the elevation point
            font=dict(size=12, color="black"),)
        

        fig.update_layout(
            template="plotly_white", # Sets initial white theme
            plot_bgcolor="white",
            paper_bgcolor="white",
            xaxis_title="Distance along path (m)",
            yaxis_title="Elevation (m)",
            hovermode="x",
            # Set the buffer space here
            xaxis=dict(
                showgrid=True,gridcolor="lightgray",gridwidth=0.5,
                zeroline=False,showline=True,linecolor="black",
                mirror=True
            ),
            yaxis=dict(showgrid=True,gridcolor="lightgray",
                gridwidth=0.5,zeroline=False,showline=True,linecolor="black",
                mirror=True,autorange=True # Ensures topography is fully visible
            ),
            margin=dict(l=60, r=40, t=50, b=60),height=500
        )

    return fig

def build_combined_borehole_figure(bh_ids, bh_projections, rock_color_map):
    fig = go.Figure()
    valid_indices = []
    # space boreholes out along the x-axis by index (0, 1, 2...) rather than their actual profile distance
    for x_pos, target_id in enumerate(bh_ids):
        # Find the specific borehole data from your projections list
        bh = next((b for b in bh_projections if str(b.get('id')) == str(target_id) or str(b.get('bh_index')) == str(target_id)), None)
        
        if not bh: continue
        
        valid_indices.append(x_pos)
        
        # for layer in bh['layers']:
        for layer in bh.get('layers', []):
            # Use Elevation (as in your original code)
            z_bottom = bh['elev'] - float(layer['Top'])
            z_top = bh['elev'] - float(layer['Bottom']) 

            # Center the box around x_pos (0, 1, 2...)
            width = 0.4 
            x_box = [x_pos - width, x_pos + width, x_pos + width, x_pos - width, x_pos - width]
            y_box = [z_top, z_top, z_bottom, z_bottom, z_top]

            rock = layer.get('LayerDescription', '').strip()
            color = rock_color_map.get(rock, "lightgray")

            fig.add_trace(go.Scatter(
                x=x_box, y=y_box,
                fill="toself",
                fillcolor=color,
                mode='lines',
                line=dict(width=0.8, color='black'),
                name=rock,
                showlegend=False,
                hovertext=f"<b>{bh['id']}</b><br>{rock}<br>Elev: {z_top:.1f} to {z_bottom:.1f}m",
                hoverinfo="text"
            ))

        # Add ID label at the top of each borehole column
        fig.add_annotation(
            x=x_pos, y=bh['elev'],
            text=f"<b>{bh['id']}</b>",
            showarrow=False, yshift=15,
            font=dict(size=12)
        )
    
    if valid_indices:
        x_min = min(valid_indices) - 1
        x_max = max(valid_indices) + 1
    else:
        x_min, x_max = -1, 1

    # Apply your preferred professional layout
    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        xaxis=dict(
            tickvals=list(range(len(bh_ids))),
            ticktext=bh_ids,
            title="Borehole ID",
            range=[x_min, x_max],
            showgrid=False,
            linecolor="black", mirror=True
        ),
        yaxis=dict(
            title="Elevation (m.a.s.l.)",
            gridcolor="lightgray",
            linecolor="black", mirror=True
        ),
        margin=dict(l=60, r=40, t=50, b=60),
        legend=dict(title="Lithology", bordercolor="black", borderwidth=1)
    )
    
    return fig


# ----------- BOREHOLES ----------------
bh_data, rock_color_map = load_borehole_file(r"C:\Users\au646858\Downloads\boreholes_Gende_Rige_test.bor")
# bh_data = None 
# rock_color_map = None


model_frame = TEMframe.from_pandas(pd.read_csv("test_models_day4.csv"))
# model_frame = TEMframe.from_pandas(pd.read_csv('test_models_Dollow.csv'))

def preprocess_new_df(new_df):
    # 1. Identify which columns are attributes vs which are layer data
    # Add any attribute here that you want to filter by in the UI
    attributes = ['date', 'daytime', 'elevation','Data Residual', 'DOI', 'Number of Gates']
    color_master_map = {}

    # 2. Build the aggregation dictionary
    agg_dict = {
        'resistivity': lambda x: list(x),
        'top_depth': lambda x: list(x),
        'bottom_depth': lambda x: list(x),}
        
    
    groupby_cols = ['site_id', 'latitude', 'longitude', 'elevation']
    existing_attrs = [col for col in attributes if col in new_df.columns]
    # print("EXISTING ATTRS", existing_attrs)
    
    # For every attribute, just take the first occurrence in the group
    for col in existing_attrs:
        if col not in groupby_cols:
            agg_dict[col] = 'first'

    # 3. Group and aggregate
    df_wide = new_df.groupby(groupby_cols).agg(agg_dict).reset_index()

    # 4. Create the 'Depths' column
    def extract_depth_interfaces(row):
        return row['top_depth'] + [row['bottom_depth'][-1]]
    
    df_wide['Depths'] = df_wide.apply(extract_depth_interfaces, axis=1)
    
    # 5. Make a global color for attr to be used even when the user changes attribute
    for attr in existing_attrs:
            if attr in new_df.columns:
                # CLEAN the unique values: string -> no .0 -> stripped
                unique_vals = (new_df[attr].astype(str)
                            .str.replace(r'\.0$', '', regex=True)
                            .str.strip()
                            .unique())
                unique_vals = sorted(unique_vals.tolist())            
                palette = px.colors.qualitative.Light24 # 26 distinct colors
                
                # Create the map for this attribute
                color_master_map[attr] = {val: palette[i % len(palette)] for i, val in enumerate(unique_vals)}

    return df_wide, color_master_map, existing_attrs

def get_numeric_colors(values, cmap_name='jet'): # to cheat plotly with hex string colors to prevent it from crashing
    """Maps a list of numbers to a list of Hex strings."""
    try:
        # Convert to numpy for easy math
        vals = np.array(values, dtype=float)
        vmin, vmax = np.nanmin(vals), np.nanmax(vals)
        
        # Handle case where all values are the same
        if vmin == vmax:
            return ['#440154'] * len(vals) # Default Viridis purple
            
        norm = mcolors.Normalize(vmin=vmin, vmax=vmax)
        cmap = plt.get_cmap(cmap_name)
        
        return [mcolors.to_hex(cmap(norm(v))) for v in vals]
    except:
        return ['grey'] * len(values)

# Apply it
df, color_master_map, existing_attrs = preprocess_new_df(model_frame)

# -------------------------------------------------------------
def paper_to_geo(px, py, view):
    if not view or "bbox" not in view or view["bbox"] is None:
        print("❌ No bbox yet")
        return None

    bbox = view["bbox"]

    # Extract all lon/lat pairs
    try:
        lons = [p[0] for p in bbox]
        lats = [p[1] for p in bbox]
    except Exception as e:
        print("❌ Bad bbox format:", bbox)
        return None

    lon_min = min(lons)
    lon_max = max(lons)
    lat_min = min(lats)
    lat_max = max(lats)

    # 📌 IMPORTANT:
    # paper y increases downward → geographic lat decreases
    lon = lon_min + px * (lon_max - lon_min)
    lat = lat_min + py * (lat_max - lat_min)

    # print("BBOX received:", view.get("bbox"))
    # print("px, py:", px, py)
    # print("Computed lon/lat:", lon, lat)
    # print("lon_min/max, lat_min/max:", lon_min, lon_max, lat_min, lat_max)

    return [lon, lat]

# ------------------------- double click line - calculate the distance between clicks in meters -------------------------
def haversine_distance(p1, p2):
    """Calculates distance between two [lon, lat] points in meters."""
    lon1, lat1 = np.radians(p1)
    lon2, lat2 = np.radians(p2)
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371000  # Radius of earth in meters
    return c * r

def parse_polyline_path(path_str, view):
    """Parses SVG path into geographic [lon, lat] pairs."""
    # Find all numbers in the string
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", path_str)
    points = []
    
    # Group numbers into pairs (x, y)
    for i in range(0, len(nums), 2):
        x_paper = float(nums[i])
        y_paper = float(nums[i+1])
        
        # Convert paper (0-1) to Geo
        geo_pt = paper_to_geo(x_paper, y_paper, view)
        if geo_pt:
            points.append(geo_pt)
            
    return points

def project_station_onto_polyline(station_pt, polyline_coords):
    """
    station_pt: [lon, lat]
    polyline_coords: [[lon1, lat1], [lon2, lat2], ...]
    Returns: (best_x_dist, min_dist_to_line_m)
    """
    best_x = 0
    min_dist_to_line = float('inf')
    cum_dist = 0
    
    for i in range(len(polyline_coords) - 1):
        A = np.array(polyline_coords[i])
        B = np.array(polyline_coords[i+1])
        P = np.array(station_pt)
        
        seg_len = haversine_distance(A, B)
        if seg_len == 0: continue
        
        # Vector math for projection
        # t is the fraction along the segment (0 to 1)
        ap = P - A
        ab = B - A
        t = np.dot(ap, ab) / np.dot(ab, ab)
        t = np.clip(t, 0, 1)
        
        # Closest point on this segment
        closest_pt = A + t * ab
        dist_to_seg = haversine_distance(P, closest_pt)
        
        if dist_to_seg < min_dist_to_line:
            min_dist_to_line = dist_to_seg
            best_x = cum_dist + (t * seg_len)
            
        cum_dist += seg_len
        
    return best_x, min_dist_to_line

def get_station_projections(polyline_coords, df, search_radius_m=settings.radius):
    stations_on_line = []
    
    for i, row in df.iterrows():
        s_pt = [row['longitude'], row['latitude']]
        
        # Use our new linear projection
        dist_x, dist_to_line = project_station_onto_polyline(s_pt, polyline_coords)
        
        if dist_to_line <= search_radius_m:
            stations_on_line.append({
                'df_index': i,
                'dist_x': dist_x,
                'elev': row['elevation'],
                'res': row['resistivity'],
                'id': row.get('site_id', i)
            })
            
    # Sort by distance along path so the plot is ordered left-to-right
    return sorted(stations_on_line, key=lambda x: x['dist_x'])

#-------------------------------------------
def interpolate_nearest(df, samples, radius=settings.radius):
    """
    Efficient spatial lookup for resistivity and elevation.
    samples: array of [lon, lat] pairs.
    """
    coords = df[["longitude", "latitude"]].values
    tree = cKDTree(coords)

    # Query nearest points --- Nearest-Neighbor interpolation.
    dists, idxs = tree.query(samples)

    res_models = []
    elevations = []

    for dist, idx in zip(dists, idxs):
        # radius is in degrees; roughly 0.001 deg ~ 111m
        if radius is not None and dist > radius:
            res_models.append(None) 
            elevations.append(np.nan)
        else:
            res_models.append(df.iloc[idx]["resistivity"])
            elevations.append(df.iloc[idx]["elevation"]) 

    return res_models, elevations, dists, idxs

def get_polyline_profile(coords, section_data, resolution_m=10.0):
    """
    Takes polyline points, generates equal-distance sample points in meters,
    and returns coords and distances for plotting.
    """
    all_x_coords = []
    all_lons = []
    all_lats = []
    total_dist = 0.0

    for i in range(len(coords) - 1):
        p_start, p_end = coords[i], coords[i+1]
        seg_length = haversine_distance(p_start, p_end)
        
        num_samples = max(2, int(seg_length / resolution_m))
        
        lons = np.linspace(p_start[0], p_end[0], num_samples)
        lats = np.linspace(p_start[1], p_end[1], num_samples)
        
        # Distance along this specific segment
        seg_dist = np.linspace(0, seg_length, num_samples) + total_dist
        
        # Filter duplicates at vertices
        start_idx = 1 if i > 0 else 0
        all_x_coords.extend(seg_dist[start_idx:])
        all_lons.extend(lons[start_idx:])
        all_lats.extend(lats[start_idx:])
        
        total_dist += seg_length
        
    return np.array(all_x_coords), np.array(all_lons), np.array(all_lats)

def plot_section_NOT_IN_USE(x, y_depth, res_models, elev=None, title="Resistivity Section"):
    # 1. Prepare Z Data (Depth x Distance)
    Z_clean = [np.full(len(y_depth), np.nan) if r is None else r for r in res_models]
    Z_matrix = np.array(Z_clean).T  # Transpose to get [Depth, Distance]
    Z_log = np.log10(Z_matrix)


    # 2. Prepare Y Data (Topography)
    if elev is not None:
        # Create a 2D mesh of actual elevations
        # This results in a matrix where each column follows the surface terrain
        Y_grid = np.array([elev - d for d in y_depth])
        
        # We take the average elevation profile to define the Y-axis tick labels
        # but the heatmap needs to know the full extent.
        y_axis_values = Y_grid[:, 0] # Reference vertical slice
    else:
        Y_grid = np.array([-d for d in y_depth])
        y_axis_values = -y_depth

    # 3. Create Heatmap
    # Note: If your Plotly version struggles with 2D Y in go.Heatmap, 
    # we use the 'x', 'y' coordinates as 1D and the 'z' as the matrix.
    standard_colorscale = []
    for i in range(256):
        fraction = i / 255
        rgba = settings.cmap(fraction) 
        color_str = f"rgb({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)})"
        standard_colorscale.append([fraction, color_str])


    # fig = go.Figure(data=go.Contour(
    fig = go.Figure(data=go.Heatmap(
        z=Z_log,
        x=x,
        # Use the first column of the grid as the Y scale
        y=Y_grid[:, 0] if elev is not None else -y_depth, #Y_grid[:, 0]
        colorscale=standard_colorscale,
        zmin=np.log10(settings.res_min),
        zmax=np.log10(settings.res_max),

        coloraxis="coloraxis",

        # colorbar=dict(
        #     title="Resistivity (Ω·m)",
        #     tickvals=[0, 1, 2, 2.47], 
        #     ticktext=["1", "10", "100", "300"]
        # ),
        hoverinfo="all",
        connectgaps=False,
        hoverongaps=False
    ))

    # # --------- 3D plot --------- might be useful later ------ from here
    # fig = go.Figure(data=go.Surface(
    #     z=Y_grid,        # The actual elevations (Topography)
    #     x=x,             # Distances
    #     y=np.zeros_like(x), # Keep it on a single plane (2D slice)
    #     surfacecolor=Z_log, # This applies the resistivity colors
    #     colorscale=standard_colorscale,
    #     showscale=True
    # ))

    # # Force the camera to a "Side View" to look like a 2D section
    # fig.update_layout(
    #     scene=dict(
    #         camera=dict(eye=dict(x=0, y=-2, z=0)), # View from the side
    #         xaxis_title="Distance",
    #         zaxis_title="Elevation",
    #         yaxis_visible=False # Hide the depth thickness
    #     )
    # )
    # # --------- 3D plot --------- might be useful later ------ to here
    
    
    if elev is not None:
        fig.add_trace(go.Scatter(
            x=x, y=elev,
            mode='lines',
            line=dict(color='black', width=1.5, dash='dash'),
            coloraxis="coloraxis"
            # name='Topography Line'
        ))

    # 4. Final Layout Fixes
    fig.update_layout(
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title="Elevation (m)" if elev is not None else "Depth (m)",
        plot_bgcolor="white",
        hovermode="x",
        # This is critical: ensures the axis shows the full depth range
        yaxis=dict(
            autorange=True,fixedrange=False,
            # If using depths without elevation, reverse the axis
            # range=[np.nanmin(Y_grid), np.nanmax(Y_grid)] if elev is not None else None
        )
    )

    # 2. Add Layout Styling (White Background + Grid + Buffer)
    fig.update_layout(
        template="plotly_white", # Sets initial white theme
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title="Distance along path (m)",
        yaxis_title="Elevation (m)",
        # Set the buffer space here
        xaxis=dict(
            # range=[min_x - buffer, max_x + buffer],
            showgrid=True,gridcolor="lightgray",gridwidth=0.5,zeroline=False,showline=True,linecolor="black",mirror=True),
        yaxis=dict(
            showgrid=True,gridcolor="lightgray",gridwidth=0.5,zeroline=False,showline=True,linecolor="black",mirror=True,
            autorange=True # Ensures topography is fully visible
        ),
        margin=dict(l=60, r=40, t=50, b=60),
        height=500
    )
    return fig

def create_blocky_polygons(stations_on_line, depths, bar_width=settings.column_width):
    """
    Creates the discrete vertical columns at specific station locations.
    """
    traces = []
    if not stations_on_line: return go.Figure()

    # 1. Collect all x positions to calculate buffers
    x_coords = [s['dist_x'] for s in stations_on_line]
    min_x, max_x = min(x_coords), max(x_coords)
    

    for s in stations_on_line:
        x_center = s['dist_x']
        surface = s['elev']
        res_values = s['res']
        
        for j in range(len(depths) - 1):
            val = res_values[j]
            if val <= 0 or np.isnan(val): continue
            
            top, bottom = surface - depths[j], surface - depths[j+1]
            
            x_box = [x_center - bar_width/2, x_center + bar_width/2, 
                     x_center + bar_width/2, x_center - bar_width/2, x_center - bar_width/2]
            y_box = [top, top, bottom, bottom, top]
            
            sounding_idx = s.get('df_index')
                    
            traces.append(go.Scatter(
                x=x_box, y=y_box, 
                fill="toself",                
                fillcolor=resist_to_rgba(val),
                marker=dict(color=resist_to_rgba(val)), 
                mode='lines', line=dict(width=0.1,color="black"),                                
                customdata=[sounding_idx, x_center] * len(x_box),
                name=f"Station {sounding_idx}",
                hoveron='fills', hoverinfo="all", text=f"Res: {val:.1f} Ωm",
                showlegend=False))

    fig = go.Figure(data=traces)
    fig.update_layout(dragmode='pan', hovermode='closest')   

# 2. Add Layout Styling (White Background + Grid + Buffer)
    fig.update_layout(
        template="plotly_white", # Sets initial white theme
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title="Distance along path (m)",
        yaxis_title="Elevation (m)",
        hovermode="x",
        # Set the buffer space here
        xaxis=dict(showgrid=True,gridcolor="lightgray",gridwidth=0.5,zeroline=False,
            showline=True,linecolor="black",mirror=True),
        yaxis=dict(showgrid=True,gridcolor="lightgray",gridwidth=0.5,
            zeroline=False,showline=True,linecolor="black",
            mirror=True, autorange=True # Ensures topography is fully visible
        ),
        margin=dict(l=60, r=40, t=50, b=60),height=500)

    return fig

def combine_sections_final(all_x, y_depth, res_models, elevations, stations_on_line, bar_width=40):
    """
    Combines the heatmap background with discrete block overlays.
    """
    # 1. Create Heatmap
    # fig = plot_section(all_x, y_depth, res_models, elev=elevations, title="Combined Section")
    fig = plot_section_topographic(all_x, y_depth, res_models, elev=elevations, title="Combined Section")
    for trace in fig.data:
        trace.opacity = 0.5
        fig.add_trace(trace)
    
    # 2. Add Blocky traces
    blocky_fig = create_blocky_polygons(stations_on_line, y_depth, bar_width)
    for trace in blocky_fig.data:
        trace.opacity = 1
        fig.add_trace(trace)
        
    return fig

# ---------- for hover Marker -------------
def get_geo_at_distance(polyline, target_dist):
    """Finds [lon, lat] at target_dist meters from the start of the polyline."""
    cum_dist = 0
    for i in range(len(polyline) - 1):
        p1, p2 = polyline[i], polyline[i+1]
        seg_len = haversine_distance(p1, p2)
        
        if cum_dist + seg_len >= target_dist:
            # The point is on this segment
            remainder = target_dist - cum_dist
            fraction = remainder / seg_len
            
            lon = p1[0] + fraction * (p2[0] - p1[0])
            lat = p1[1] + fraction * (p2[1] - p1[1])
            return [lon, lat]
        
        cum_dist += seg_len
    return polyline[-1] # Fallback to end

def plot_section_topographic(x, y_depth, res_models, elev, title="Resistivity Section"):

    fig = go.Figure()

    # We assume 'x' and 'elev' are arrays of the same length (e.g., every 10m)
    # resolution determines the width of each vertical "slice"
    res_m = x[1] - x[0] if len(x) > 1 else 10

    # 1. Plot the "Background" Data as vertical columns
    for i in range(len(x)):
        x_center = x[i]

        if elev is not None:
            surface = elev[i]
        else: 
            return no_update
            
        res_values = res_models[i]
        
        if res_values is None: continue

        for j in range(len(y_depth) - 1):
            val = res_values[j]
            if val <= 0 or np.isnan(val): continue
            
            # SHIFT HAPPENS HERE: Elevation - Depth
            top = surface - y_depth[j]
            bottom = surface - y_depth[j+1]

            x_box = [x_center - res_m/2, x_center + res_m/2, x_center + res_m/2, x_center - res_m/2]
            y_box = [top, top, bottom, bottom]

            # Create a "pixel" rectangle for this part of the interpolation
            fig.add_trace(go.Scatter(
                x=x_box,y=y_box,
                fill="toself", 
                fillcolor=resist_to_rgba(val), 
                mode='lines', line=dict(width=0),                                             
                customdata=[x_center] * len(x_box),
                hoverinfo="text", text=f"Res: {val:.1f} Ωm",
                showlegend=False))

    # 2. Add the Topography Line (The "Staircase")
    fig.add_trace(go.Scatter(
        x=x, y=elev,
        mode='lines',showlegend=False,
        line=dict(color='black', width=2, shape='hv'), ))

    fig.update_layout(
        template="plotly_white", 
        plot_bgcolor="white",
        paper_bgcolor="white",
        xaxis_title="Distance along path (m)",
        yaxis_title="Elevation (m)",
        xaxis=dict(showgrid=True,gridcolor="lightgray",gridwidth=0.5,zeroline=False,showline=True,linecolor="black",mirror=True),
        yaxis=dict(showgrid=True,gridcolor="lightgray",gridwidth=0.5,zeroline=False,showline=True,linecolor="black",mirror=True,
                autorange=True), # Ensures topography is fully visible
        margin=dict(l=60, r=40, t=50, b=60),
        height=500)
    
    return fig

# ---------- STEP PLOT -------------
def generate_res_step_graph(row, row_index, label=None, step_color='red'):
    # --- 1. Data Extraction from the Pandas Row ---
    # Using .get() to avoid errors if a column is missing
    res = np.array(row.get('resistivity', [])).astype(float)
    top = np.array(row.get('top_depth', [])).astype(float)
    bottom = np.array(row.get('bottom_depth', [])).astype(float)
    
    # DOI handling (adjusting to your attribute structure)
    doi_val = row.get('DOI', np.nan)
    # If DOI is a list [val1, val2], take index 1; otherwise take the value
    doi = doi_val[1] if isinstance(doi_val, (list, np.ndarray)) else doi_val
    
    # --- 2. Validation ---
    valid = np.isfinite(res) & np.isfinite(top) & np.isfinite(bottom)
    res, top, bottom = res[valid], top[valid], bottom[valid]

    if len(res) == 0:
        return go.Figure().add_annotation(text="No valid layers", showarrow=False)

    # --- 3. Create the Figure ---
    fig = go.Figure()

    # Step-post logic: add last bottom and last res to close the polygon
    z_coords = np.append(top, bottom[-1])
    res_coords = np.append(res, res[-1])

    fig.add_trace(go.Scatter(
        x=res_coords,
        y=z_coords,
        mode='lines',
        line=dict(shape='hv', width=3, color=step_color),
        name=label or f"Sounding {row_index}"
    ))

    # Add DOI Line
    if pd.notnull(doi) and doi > 0:
        fig.add_hline(
            y=doi, 
            line_dash="dash", 
            line_color="gray", 
            annotation_text=f"DOI ({doi:.1f}m)", 
            annotation_position="bottom right"
        )

    # --- 4. Layout ---
    fig.update_layout(
        xaxis=dict(title="Resistivity (Ohm-m)", type="log", gridcolor='lightgray',
            linecolor='black',      # Color of the axis line
            linewidth=1,            # Thickness of the border
            mirror=True,            # Adds the line to the top as well, creating a box
            dtick=1,                # Ensures minor gridlines/labels are hidden
            minor=dict(showgrid=True, ticks=""),
            range=[0, 3]            # LOG LIMITS: 10^0 to 10^4 (i.e., 1 to 10,000 Ohm-m) change this to [0, 3] for 1 to 1,000 Ohm-m
        ),
        yaxis=dict(title="Depth (m)", autorange="reversed", gridcolor='lightgray',
            linecolor='black',
            linewidth=1,
            mirror=True,),
        template="plotly_white",
        margin=dict(l=50, r=40, t=50, b=50), # Slightly more margin for labels
        plot_bgcolor='white'
    )

    return fig

def generate_res_step_graph_elev(row, row_index, label=None, elevation=None,step_color='red'):
    res = np.array(row.get('resistivity', [])).astype(float)
    top = np.array(row.get('top_depth', [])).astype(float)
    bottom = np.array(row.get('bottom_depth', [])).astype(float)
    
    valid = np.isfinite(res) & np.isfinite(top) & np.isfinite(bottom)
    res, top, bottom = res[valid], top[valid], bottom[valid]

    if len(res) == 0:
        return go.Figure().add_annotation(text="No valid layers", showarrow=False)

    # Calculate Z coordinates based on Depth or Elevation
    if elevation is not None:
        # Elevation = Surface Elevation - Depth
        z_coords = np.append(elevation - top, elevation - bottom[-1])
        y_range = [np.min(z_coords) - 5, np.max(z_coords) + 5 ]
        y_title = "Elevation"
    else:
        z_coords = np.append(top, bottom[-1])
        y_range = [np.min(z_coords) - 5, np.max(z_coords) + 5]
        y_title = "Depth (m)"

    res_coords = np.append(res, res[-1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=res_coords,
        y= z_coords,
        mode='lines',
        line=dict(shape='hv', width=3, color=step_color),
        name=label or f"Sounding {row_index}"
    ))
    
    fig.update_layout(
        yaxis=dict(title=y_title, range=y_range, autorange=False),
        xaxis=dict(type="log", title="Resistivity (Ohm-m)", minor=dict(showgrid=False, ticks="")),
        showlegend=True,
        legend=dict(
            yanchor="bottom",
            y=0.02,             # Slightly above the bottom axis
            xanchor="left",
            x=0.02,             # Slightly to the right of the left axis
            bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent white
            bordercolor="Black",
            borderwidth=1
        ),
        margin=dict(l=60, r=20, t=30, b=50)
    )
    return fig

def build_combined_step_figure(df, indices,use_elevation=True):
    fig = go.Figure()
    
    # 1. Define custom color list: Red first, then the rest of the Plotly palette
    # We remove 'red' (or similar hex) from the standard list to prevent duplicates
    standard_colors = [c for c in px.colors.qualitative.Plotly if c.lower() != '#ef553b'] # #ef553b is Plotly Red
    colors = ['red'] + standard_colors
    
    # colors = px.colors.qualitative.Plotly
    
    for count,idx in enumerate(indices):
        # IMPORTANT: df_index vs iloc mismatch handled
        i = int(idx) if str(idx).isdigit() else idx
        row = df.loc[i] if i in df.index else df.iloc[int(i)]

        elev_val = row.get('elevation') if use_elevation else None

        chosen_color = colors[count % len(colors)]
        
        if elev_val is not None:
            one = generate_res_step_graph_elev(row, idx, elevation=elev_val, step_color=chosen_color)
        else:
            one = generate_res_step_graph(row, idx, step_color=chosen_color)

        # Copy traces from the single figure into combined fig
        for tr in one.data:
            # Give each sounding a legend label
            tr.name = f"{idx}"
            tr.showlegend = True
            fig.add_trace(tr)

    fig.update_layout(
        # title="Combined step plots",
        legend_title="Station",
        xaxis=dict(title="Resistivity (Ohm-m)", type="log", 
                    gridcolor='lightgray',        
                    linecolor='black',
                    linewidth=1,
                    mirror = True,
                    dtick=1, 
                    minor = dict(showgrid=True, ticks=""),
                    range=[0,3]),
        yaxis=dict(title="Depth (m)", gridcolor='lightgray',
                   linecolor ='black',
                   linewidth = 1, 
                   mirror = True,
                   ),
                showlegend=True,
        legend=dict(
            yanchor="bottom",
            y=0.02,             # Slightly above the bottom axis
            xanchor="left",
            x=0.02,             # Slightly to the right of the left axis
            bgcolor="rgba(255, 255, 255, 0.7)", # Semi-transparent white
            bordercolor="Black",
            borderwidth=1),
        template="plotly_white",
        margin=dict(l=40, r=20, t=40, b=40),
        clickmode="event+select"

    )
    return fig

# ------------------- draggable_window -------------------
def create_draggable_window(win_id, title, content, width="400px",height="700px"):
    if hasattr(content, 'layout'):
        body = dcc.Graph(
            figure=content, 
            style={"height": "100%", "width": "100%"}, 
            config={'responsive': True, 'displayModeBar': False}
        )
    else:
        body = content

    return html.Div(
        id=win_id, 
        className="draggable-window",
        style={
            "position": "fixed", "top": "150px", "left": "200px",
            "width": width, "height": height, "backgroundColor": "white",
            "border": "2px solid #333", "zIndex": 1000, "resize": "both", 
            "overflow": "hidden", "display": "flex", "flexDirection": "column",
            "boxShadow": "8px 8px 20px rgba(0,0,0,0.4)"
        },
        children=[
            html.Div([
                html.Span(title, style={"fontWeight": "bold", "marginLeft": "10px"}),
                # This button uses a DICTIONARY index
                html.Button("✕", id={"type": "close-window", "index": win_id}, 
                           style={"float": "right", "cursor": "pointer", "color": "white", "border":"none", "background":"none"})], 
            className="window-header", 
            style={"background": "#2c3e50", "color": "white", "padding": "5px", "height": "30px", "cursor": "move"}),
            
            html.Div(body, style={"flex": "1 1 auto", "minHeight": "0", "width": "100%"}),
        ]
    )
