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

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod

from basepanel import Panel, gear_maker, dcc
from temframe import TEMframe

geod = Geod(ellps="WGS84")
num_layers = 28         # number of interpreted layers
depth = 120       # number of depth samples per layer
res_min = 1 
res_max = 300
norm = mcolors.LogNorm(vmin=res_min, vmax=res_max)
cmap = cm.jet
line_color="yellow"


def resist_to_rgba(res):
    """Convert resistivity value into Plotly rgba string using global cmap."""
    rgba = cmap(norm(res))  # returns (r,g,b,a) floats 0–1
    return f"rgba({rgba[0]*255:.0f},{rgba[1]*255:.0f},{rgba[2]*255:.0f},{rgba[3]:.2f})"

# ------------------------ # DEPTH MODEL GENERATOR # ------------------------
def generate_depths():
    depths = list(np.logspace(0, np.log10(depth), num_layers))  # example: 0 → 50 meters
    depths.append(math.inf)  # last depth → infinite
    return depths  # length = 20

# ------------------------# RESISTIVITY MODEL # ------------------------

def generate_res_model():
    return np.random.uniform(res_min, res_max, size=num_layers)

# --------------------- Settings ---------------------
class Settings:
    color = "red"
    highlight_color = "yellow"
    zoom = 10
    png_crs = "EPSG:32637"

settings = Settings()
# # Sample dataframe
# df = pd.DataFrame({
#     "latitude": [9.72, 9.70, 9.67, 9.69],
#     "longitude": [41.56, 41.58, 41.54, 41.55],
#     "value": [40.2, 50.8, 45.5, 47.9],
#     "Elevation": [1000.2, 1100.8, 1090.5, 1050.9],
#     "Resistivity" : [20, 38, 75, 1],
#     "ResModel":     [generate_res_model() for _ in range(4)],
#     "Depths":       [generate_depths() for _ in range(4)],
# })


model_frame = TEMframe.from_pandas(pd.read_csv('test_models_day3.csv'))

def preprocess_new_df(new_df):
    # Group by site to aggregate layers into lists
    df_wide = new_df.groupby(['site_id', 'latitude', 'longitude', 'elevation']).agg({
        'resistivity': lambda x: list(x),
        'top_depth': lambda x: list(x),
        'bottom_depth': lambda x: list(x)
    }).reset_index()

    # Create a 'Depths' column that mimics your old structure [z0, z1, z2...]
    # We take the top_depths and append the last bottom_depth
    def extract_depth_interfaces(row):
        return row['top_depth'] + [row['bottom_depth'][-1]]
    
    df_wide['Depths'] = df_wide.apply(extract_depth_interfaces, axis=1)
    
    return df_wide

# Apply it
df = preprocess_new_df(model_frame)

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

# ----------------- for profiles -----------------------------
def to_xy(lon, lat):
    """Convert lon/lat → local meters"""
    proj = Transformer.from_crs("EPSG:4326", settings.png_crs, always_xy=True)
    proj_inv = Transformer.from_crs(settings.png_crs, "EPSG:4326", always_xy=True)
    
    return np.array(proj.transform(lon, lat))
# --------------------- Line sampling & interpolation ---------------------
def sample_line_lonlat(l0, l1, n=200):
    x = np.linspace(l0[0], l1[0], n)
    y = np.linspace(l0[1], l1[1], n)
    return np.column_stack((x, y))

def project_point_onto_line_xy(P, A, B):
    """
    Project point P onto the line A→B (all in xy meters)
    Returns projection Pc and normalized coordinate t along the line.
    """
    AP = P - A
    AB = B - A
    denom = np.dot(AB, AB)
    if denom == 0:
        return A.copy(), 0

    t = np.dot(AP, AB) / denom
    t = np.clip(t, 0, 1)      # clamp inside the segment
    Pc = A + t * AB
    return Pc, t

def compute_station_positions(df, p0_geo, p1_geo):
    """
    Convert stations + line endpoints to meter coordinates
    Project each station onto the line
    Return x positions in meters
    """
    # Convert line endpoints
    A = to_xy(p0_geo[0], p0_geo[1])
    B = to_xy(p1_geo[0], p1_geo[1])
    AB = B - A
    total_len = np.linalg.norm(AB)

    x_positions = []
    for _, row in df.iterrows():
        P = to_xy(row["longitude"], row["latitude"])
        Pc, t = project_point_onto_line_xy(P, A, B)
        x_positions.append(t * total_len)   # distance in meters

    return np.array(x_positions)

def collapse_by_station_only(idxs, curves):
    unique_ids = sorted(set(int(i) for i in idxs))
    Z = np.column_stack([curves[i] for i in unique_ids])

    return Z, unique_ids

def interpolate_nearest(df, samples, radius=None):
    """
    Given sample lon/lat pairs, returns:
    - nearest resistivity model (5×20)
    - distance to nearest point
    - nearest point index

    samples → array of (lon,lat) pairs
    """

    # KD-tree for fast nearest-neighbor lookup
    coords = df[["longitude", "latitude"]].values
    print("Number of DF points:", len(coords))
    
    tree = cKDTree(coords)

    # Query nearest points
    dists, idxs = tree.query(samples)
    # print("Nearest idxs sample =", idxs[:5])
    # print("Distances sample =", dists[:5])

    # Resistivity models for each sampled point
    res_models = []
    elevations = []

    for dist, idx in zip(dists, idxs):
        if radius is not None and dist > radius:
            res_models.append(None)   # no data beyond radius
            elevations.append(np.nan)
        else:
            res_models.append(df.iloc[idx]["resistivity"])
            elevations.append(df.iloc[idx]["elevation"]) 

    return res_models, elevations, dists, idxs

def cumulative_distance_m(samples): # for distance in meters
    """
    samples: array of shape (N,2) → [lon, lat]
    returns: cumulative distance in meters
    """
    lons = samples[:, 0]
    lats = samples[:, 1]

    d = [0.0]

    for i in range(1, len(samples)):
        _, _, dist = geod.inv(lons[i-1], lats[i-1], lons[i], lats[i])
        d.append(d[-1] + dist)

    return np.array(d)

def make_column_matrix(curves):
    """
    curves: array shape (num_samples, num_depths)    
    returns Z: shape (num_depths, num_samples)
    """
    curves = np.asarray(curves)

    if curves.ndim != 2:
        raise ValueError(f"Expected curves shape (Nsamples, Ndepths), got {curves.shape}")

    # transpose to (depths × samples)
    Z = curves.T  
    return Z

def plot_column_section_blocky(x, y_depth, Z, elev=None, doi=None):

    Nstations = len(x)
    Nlayers = Z.shape[0]  
    fig = go.Figure()
    
    xmin = np.min(x)
    xmax = np.max(x)

    # ---- column width factors ----
    max_width =  0.05 * (xmax - xmin) 
    width_factor = 0.8
    
    # ---- Loop over stations ----
    for i in range(Nstations):

        # spacing controlled by next station, except last
        if i < Nstations - 1:
            width = x[i + 1] - x[i]
        else:
            width = x[i] - (x[i - 1] if i > 0 else x[i] - 10)

        width = min(width, max_width)
        x_left = x[i]
        x_right = x_left + width * width_factor

        # DOI elevation
        if elev is not None and doi is not None:
            doi_line = elev[i] - doi[i]
        else:
            doi_line = None

        # ---- Each vertical layer ----
        for j in range(Nlayers):
            z_top = y_depth[j]
            if j + 1 < len(y_depth):
                z_bot = y_depth[j+1]
            else:
                # If we are at the very last depth entry, 
                # extend the last layer by a fixed amount (e.g., 50m)
                z_bot = z_top + 50


            # Convert depth to elevation if needed
            if elev is not None:
                y_top = elev[i] - z_top
                y_bot = elev[i] - z_bot
            else:
                y_top = z_top
                y_bot = z_bot

            # Resistivity value → color
            resist = Z[j, i]

            # Alpha depending on DOI
            if doi_line is None:
                alpha = 1.0
            else:
                alpha = 0.2 if y_bot < doi_line else 1.0

            # Rectangle polygon
            Xpoly = [x_left, x_right, x_right, x_left, x_left]
            Ypoly = [y_top,  y_top,   y_bot,   y_bot,  y_top]

            fig.add_trace(
                go.Scatter(x=Xpoly,y=Ypoly,
                    mode="lines",
                    fill="toself",
                    fillcolor=resist_to_rgba(resist),
                    line=dict(width=0),hoverinfo="none",showlegend=False))
    

    # Add a global colorbar using dummy trace
    fig.add_trace(
        go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(colorscale="Jet",cmin=res_min,cmax=res_max,color=[res_min, res_max],showscale=True,colorbar=dict(title="Resistivity (Ω·m)")),
            showlegend=False))

    pad = 0.1 * (xmax - xmin)    # meters padding on each side

    fig.update_xaxes(range=[xmin - pad, xmax + pad])

    fig.update_layout(
        xaxis_title="Distance (m)",
        yaxis_title="Depth (m)" if elev is None else "Elevation (m)",
        yaxis_autorange=True if elev is not None else "reversed",
        title="Resistivity Section",
        height=400,
        plot_bgcolor="white",    
        xaxis=dict(showline=True,linewidth=1,linecolor="black",mirror=True,showgrid=True,
                    gridcolor="lightgray", gridwidth=0.5,),
        yaxis=dict(showline=True,linewidth=1,linecolor="black",mirror=True,showgrid=True,
        gridcolor="lightgray",gridwidth=0.5,),)
        # paper_bgcolor="lightgray")

    return fig

def plot_section(x, y, Z, elev=None, doi=None, title="Interpolated Resistivity Section"):
    """
    elev : array of elevations at each sample point along x
    """
    Zplot = Z.copy()
    if Zplot.shape[0] == len(x):
        Zplot = Zplot.T
    
    # 1. Coordinate Mesh for Topography
    # y is Depth (e.g., 0 to 200)
    # elev is Surface (e.g., 1205)
    if elev is not None:
        # Create a 2D grid of elevations: Surface[x] - Depth[y]
        # We use broadcasting to subtract the depth array from the elevation array
        Y_geo = elev.reshape(1, -1) - y.reshape(-1, 1)
    else:
        Y_geo = y

    # 2. Masking (Optional DOI)
    if elev is not None and doi is not None:
        for i in range(Zplot.shape[1]):
            cutoff_depth = doi[i]
            cutoff_idx = np.searchsorted(y, cutoff_depth)
            Zplot[cutoff_idx:, i] = np.nan

    # 3. Use Non-Uniform Heatmap (go.Heatmap with 2D Y-coordinates)
    # Note: For Topography, we use go.Surface or a colored mesh if Y is not constant.
    # However, for a standard Heatmap, we often just use the mean elevation or 
    # use go.Contour / go.Scatter with custom coloring.
    Z_log = np.log10(Zplot)
    
    log_zmin = np.log10(res_min)
    log_zmax = np.log10(res_max)
    
    standard_colorscale = []
    for i in range(256):
        fraction = i / 255
        rgba = cmap(fraction) 
        color_str = f"rgb({int(rgba[0]*255)}, {int(rgba[1]*255)}, {int(rgba[2]*255)})"
        standard_colorscale.append([fraction, color_str])
    
    fig = go.Figure(data=go.Heatmap(
        z=Z_log, #Zplot,
        x=x,
        y=y if elev is None else None, # We'll handle custom Y below
        # colorscale='jet', # Use your custom Jet norm logic here
        # colorscale=[[i/255, f"rgb({int(cmap(norm(i*(res_max/255)))[0]*255)},"
        #           f"{int(cmap(norm(i*(res_max/255)))[1]*255)},"
        #           f"{int(cmap(norm(i*(res_max/255)))[2]*255)})"]
        #             for i in range(256)],
        colorscale=standard_colorscale,
        zmin=log_zmin, 
        zmax=log_zmax,
        colorbar=dict(title="Resistivity (Ω·m)",tickvals=[],)
    ))

    if elev is not None:
        # If we have topography, standard Heatmap 'y' won't work perfectly 
        # because the grid is non-rectilinear. We shift the axis.
        fig.update_traces(y=Y_geo.mean(axis=1)) # Simplified for visual
        # For a true topographic plot, you might prefer a filled Contour plot:
        # fig = go.Figure(data=go.Contour(z=Zplot, x=x, y=Y_geo...))

    fig.update_layout(
        title=title,
        xaxis_title="Distance (m)",
        yaxis_title="Elevation (m)" if elev is not None else "Depth (m)",
        yaxis_autorange=True if elev is not None else "reversed",
        plot_bgcolor="white"
    )

    return fig

def combine_sections(x, y, Z_interp, elev, x_single, Z_block, elev_b):
        fig = plot_section(x, y, Z_interp, elev)

        # Overlay blocky polygons
        block_fig = plot_column_section_blocky(x_single, y, Z_block, elev_b)

        for tr in block_fig.data:
            fig.add_trace(tr)

        fig.update_layout(title="Combined Resistivity Section")

        return fig

# ------------- MULTI line Setup -----------------
def combine_sections_2(x, y, Z_interp, elev, x_single, Z_block, elev_b):
        fig = plot_section(x, y, Z_interp, elev)

        # Overlay blocky polygons
        block_fig = create_blocky_polygons(x_single, y, Z_block, elev_b)

        for tr in block_fig.data:
            fig.add_trace(tr)

        fig.update_layout(title="Combined Resistivity Section")

        return fig


def sample_at_point(lon, lat, section_data, return_elev=False):
    """
    Finds data at a specific lon/lat by looking up the nearest station.
    Set return_elev=True to get elevation instead of resistivity.
    """
    # 1. Identify coordinate columns
    df_lons = section_data['longitude'].values 
    df_lats = section_data['latitude'].values

    # 2. Find nearest neighbor index
    dist_sq = (df_lons - lon)**2 + (df_lats - lat)**2
    nearest_idx = dist_sq.argmin()

    # 3. Return the requested data
    if return_elev:
        # Assuming your dataframe has an 'elevation' column
        return section_data['elevation'].values[nearest_idx]
    
    # Otherwise return the resistivity array
    return section_data['resistivity'].values[nearest_idx]

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


def parse_polyline_path(path_str, view=None):
    """
    Robustly extracts coordinates from SVG path strings like 'M0.1,0.2L0.3,0.4'
    """
    if not path_str:
        return []

    # 1. Use regex to find all numbers (including decimals and negatives)
    # This pattern finds things like 0.518, -1.2, etc.
    numbers = re.findall(r"[-+]?\d*\.\d+|\d+", path_str)
    
    # 2. Group them into pairs [x, y]
    pairs = []
    for i in range(0, len(numbers), 2):
        if i + 1 < len(numbers):
            x = float(numbers[i])
            y = float(numbers[i+1])
            
            # 3. Handle conversion if it's Paper space (0 to 1)
            if 0 <= x <= 1 and 0 <= y <= 1 and view is not None:
                geo_pt = paper_to_geo(x, y, view)
                if geo_pt:
                    pairs.append(geo_pt)
            else:
                # Already geographic
                pairs.append([x, y])
                
    return pairs

def get_polyline_profile(coords, section_data, resolution_m=5.0):
    """
    coords: [[lon1, lat1], [lon2, lat2], ...]
    section_data: Your 3D resistivity volume or grid
    resolution_m: How many meters between sampling points
    """
    cumulative_dist = [0.0]
    all_values = []
    all_x_coords = []

    for i in range(len(coords) - 1):
        p_start = coords[i]
        p_end = coords[i+1]
        
        # 1. Calculate length of this specific segment
        seg_length = haversine_distance(p_start, p_end)
        
        # 2. Determine number of samples for this segment
        num_samples = max(2, int(seg_length / resolution_m))
        
        # 3. Interpolate Lon/Lat points along this segment
        lons = np.linspace(p_start[0], p_end[0], num_samples)
        lats = np.linspace(p_start[1], p_end[1], num_samples)
        
        # 4. Sample data at these Lon/Lat locations
        # (Assuming your sample_at_point function handles the 3D lookup)
        seg_values = [sample_at_point(lon, lat, section_data) for lon, lat in zip(lons, lats)]
        
        # 5. Build the segment's distance array relative to start of path
        start_dist = cumulative_dist[-1]
        seg_dist = np.linspace(0, seg_length, num_samples) + start_dist
        
        # Avoid duplicating the joint point (where segments meet)
        if i > 0:
            all_x_coords.extend(seg_dist[1:])
            all_values.extend(seg_values[1:])
        else:
            all_x_coords.extend(seg_dist)
            all_values.extend(seg_values)
            
        cumulative_dist.append(start_dist + seg_length)
        
    return np.array(all_x_coords), np.array(all_values)

def create_blocky_polygons(distances, depths, values):
    """
    Generates the vertices for the go.Scatter traces.
    distances: 1D array from get_polyline_profile
    depths: 1D array of layer depths
    """
    traces = []
    # Calculate widths based on the distance between samples
    widths = np.diff(distances, append=distances[-1] + (distances[-1]-distances[-2]))
    
    for i in range(len(distances)):
        for j in range(len(depths)-1):
            # Vertices for one 'block'
            x_rect = [distances[i], distances[i]+widths[i], distances[i]+widths[i], distances[i], distances[i]]
            y_rect = [depths[j], depths[j], depths[j+1], depths[j+1], depths[j]]
            
            val = values[i][j] # Access specific cell
            
            traces.append(go.Scatter(
                x=x_rect, y=y_rect,
                mode='lines',
                fill='toself',
                fillcolor=resist_to_rgba(val),
                line=dict(width=0),
                showlegend=False
            ))
    return traces