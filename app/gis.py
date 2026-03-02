from dataclasses import field
from basepanel import *
#from database_panel import DatabasePanel
from dash import dash_table
import numpy as np
from nosj import nosj

import plotly.io as pio
from typing import Literal
import plotly.express as px
import plotly.graph_objects as go

import os
import base64
import rasterio
import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import reshape_as_image
from PIL import Image
from pyproj import Transformer
import pandas as pd
import math

import matplotlib.cm as cm
import matplotlib.colors as mcolors

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod


from Map_external_layers import GIS_helpers
from Sections_plotting import *

# Define a custom template
custom_template = {
    "layout": {
        "font": {"family": "Arial", "size": 14, "color": "black"},
        "plot_bgcolor": "white",
        "paper_bgcolor": "white",
        "margin": {"l": 50, "r": 50, "t": 50, "b": 50},
        "xaxis": {
            "showgrid": True,
            "gridcolor": "#e5e5e5",
            "zeroline": False,
            "showline": True,
            "linecolor": "black",
            "ticks": "outside",
        },
        "yaxis": {
            "showgrid": True,
            "gridcolor": "#e5e5e5",
            "zeroline": False,
            "showline": True,
            "linecolor": "black",
            "ticks": "outside",
        },
    }
}
pio.templates["custom"] = custom_template
pio.templates.default = "custom"

@nosj
class GISSettings(PanelSettings):
    # color: str = "red"
    # highlight_color: str = "yellow"
    # zoom: int = 10
    zoom: int = 14
    color: str = '#ff0000'
    highlight_color: str= '#ffff00'  # Default highlight color
    plot_attribute:  Literal['date', 'daytime', 'misfit','doi', 'Number of Gates'] = 'date'
    png_crs: str = "EPSG:32637"
    bh_color: str = 'orange'
    # geod: str = Geod(ellps="WGS84")
    res_min: int = 1
    res_max: int = 300
    # norm: str = mcolors.LogNorm(vmin=res_min, vmax=res_max)
    # cmap: str = cm.jet
    # line_color: str="yellow"
    radius: int = 50 
    column_width: int = 6
    num_labels_colorbar: int = 4
    # raster_cache_dir: str = r"C:\Users\au679476\Downloads\test_for_map_pngs_tiffs\raster_cache"
    
    show_google : str = True
    show_points : str = True
    show_tiff : str = True
    show_png : str = True
    show_boreholes : str = True

from Map_external_layers import GIS_helpers, make_safe_id_from_stem, layer_row


class GIS(Panel):
    def __init__(self, dataframe, **kwargs):
 
        self.dataframe = dataframe
        self.tiff_path = None
        self.png_path = None
        self.tiff_info = None
        self.png_info = None
        self._tiff_cache = {}
        self._png_cache = {}
 
        settings = kwargs.pop('settings', GISSettings(id = 'gis'))
       
        super().__init__(id = 'gis', settings=settings)
       
        for key, value in kwargs.items():
            setattr(self, key, value)
           
       
        self.tiff_info = self._load_tiff() if getattr(self, 'tiff_path', None) else None
        self.png_info = self._load_png() if getattr(self, 'png_path', None) else None
 
        if self.tiff_info and self.png_info:
            self._check_bounds_match()
        self.view = {}
        
    def _compute_df_center(self, dataframe):
        """Return dict(lat=..., lon=...) as the center of the dataframe points"""
        if dataframe is None or dataframe.empty:
            # fallback center (0,0)
            return dict(lat=0, lon=0)
        return dict(
            lat=dataframe["latitude"].mean(),
            lon=dataframe["longitude"].mean()
        )

    def _build_map_layers(self, show_google, show_tiff, show_png, google_op, tiff_op, png_op):
            layers = []

                # --- Bottom layer: Google Earth ---
            if show_google:
                layers.append({
                "sourcetype": "raster",
                "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"],
                "sourceattribution": "Google Earth (C)",
                "below": "traces",  # keep it below the points
                "opacity": google_op,
                })

            # --- TIFF layer ---
            if show_tiff and self.tiff_info:
                l, b, r, t = self.tiff_info["bounds"]
                layers.append({
                    "below": "traces",
                    "sourcetype": "image",
                    "source": self.tiff_info["image"],
                    "coordinates": [[l, t], [r, t], [r, b], [l, b]],
                    "opacity": tiff_op,
                })

            # --- PNG layer ---
            if show_png and self.png_info:
                l, b, r, t = self.png_info["bounds"]
                layers.append({
                    "below": "traces",
                    "sourcetype": "image",
                    "source": self.png_info["image"],
                    "coordinates": [[l, t], [r, t], [r, b], [l, b]],
                    "opacity": png_op,
                })
            # print("MAP LAYERS:", len(layers))
            return layers
    
    def render(self,**kwargs):

        for key, value in kwargs.items():
            setattr(self, key, value)
        
        if not hasattr(self, 'dataframe') or self.dataframe is None:
            print("No dataframe")
            return self.empty_render()       
       
        processed_df, color_master_map, existing_attrs = preprocess_new_df(self.dataframe)

        color_map = mcolors.LogNorm(vmin=self.settings.res_min, vmax=self.settings.res_max)
 
        show_google = getattr(self, 'show_google', True)
        show_tiff = getattr(self, 'show_tiff', True)
        show_png = getattr(self, 'show_png', True)
        show_points = getattr(self, 'show_points', True)
        google_op = getattr(self, 'google_op', True)
        tiff_op = getattr(self, 'tiff_op', True)
        png_op = getattr(self, 'png_op', True)
        view = getattr(self, 'view', None)
        final_line = getattr(self,'final_line', None)
        selected_idx = getattr(self, 'selected_idx', None)
        hover_pt = getattr(self,'hover_pt', None)
        boreholes = getattr(self, 'boreholes', None)
        show_boreholes = getattr(self, 'show_boreholes', True)
        point_filters = getattr(self, 'point_filters', [])
        point_attr = getattr(self, 'point_attr', "none")
        color_map = getattr(self, 'color_map', {})      
        preview_line = getattr(self,'preview_line', None)
       
        fig = go.Figure()
        if point_attr is None:
                point_attr = "none"
        # print("POINT ATTRIBUTE",point_attr)
 
       # --- Decide zoom & center ---
        zoom = view.get("zoom") if view and "zoom" in view else self.settings.zoom
        self.settings.zoom=zoom
 
        center = view.get("center") if view and "center" in view else self._compute_df_center(processed_df)
       
        # figure without the points to keep the map on when all points are off
       
        fig = px.scatter_map(processed_df.iloc[0:0],  # empty base
                             lat="latitude",lon="longitude",zoom=zoom,center=center,)

        fig.update_layout(map_style="white-bg", coloraxis_showscale=False, 
            map_layers=[
                {   "below": 'traces',
                    "sourcetype": "raster",
                    "sourceattribution": "Google Earth (C)",
                    "source": ['https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}']
                }]) #,coloraxis_showscale=False
        # fig.update_traces(marker=dict(color=self.settings.color,showscale=False) )        # is_numeric = False
        # return fig

        if self.settings.show_points and not processed_df.empty: #self.dataframe is not None:
            display_df = pd.DataFrame() # Default to empty

            # if point_attr in self.dataframe.columns and point_filters:
            if point_attr in processed_df.columns and point_filters:
                # Normalize column: string -> no .0 -> stripped
                # col_str = self.dataframe[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                col_str = processed_df[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
               
                # Normalize filters: list of strings -> no .0 -> stripped
                if not isinstance(point_filters, list):
                    point_filters = [point_filters]
                clean_fs = [str(f).replace('.0', '').strip() for f in point_filters]
               
                # FILTER: Get rows where column is in our list of clean filters
                # display_df = self.dataframe[col_str.isin(clean_fs)]
                display_df = processed_df[col_str.isin(clean_fs)]
                   
            # # Debug inside renderer
            # print(f"RENDERER: Found {len(display_df)} points for {point_attr}")
 
            if not display_df.empty:
                # Check if it's one of our numeric columns
                numeric_cols = ['elevation', 'daytime', 'Data Residual', 'DOI']
                is_numeric = point_attr in numeric_cols
                # print("IS NUMERIC",is_numeric)
 
                if is_numeric:
                    raw_values = pd.to_numeric(display_df[point_attr], errors='coerce').tolist()
                    hex_colors = get_numeric_colors(raw_values, cmap_name='jet')
                   
                    # 1. Main Trace (The actual dots)
                    fig.add_trace(go.Scattermap(
                        lat=display_df["latitude"],
                        lon=display_df["longitude"],
                        customdata=display_df.index,# for the model plots
                        mode='markers',
                        marker=dict(size=14, opacity=0.8, color=hex_colors), # PURE HEX
                        # name=point_attr,
                        showlegend=False,
                        uid=f"pts_{point_attr}_dots"))
                   
                    # to remove the trace 1 text
                    fig.update_layout(hoverlabel=dict(namelength=0),)
 
                    # 2. Dummy Trace (Just for the Colorbar)
                    # We put one point at the first location but make it invisible (size 0)
                    colorbar_style = dict(
                        title=dict(
                            text=point_attr,
                            font = dict(color="black", size=14, family="Arial Black"),
                            side ="top",  # This is the replacement for 'titleside'
                            ),
                        thickness=20,
                        x=1.02,           # Move to the right of the map
                        xanchor="center",  
                        tickfont=dict(color="black", size=11),
                        # White background styling
                        bgcolor="rgba(255, 255, 255, 0.9)",
                        outlinecolor="white",              
                        outlinewidth=2,
                        len=0.6,          # Makes the bar a bit shorter/neater
                        yanchor="middle",
                        y=0.5             # Centers it vertically
                    )
 
                    fig.add_trace(go.Scattermap(
                        lat=[display_df["latitude"].iloc[0]],
                        lon=[display_df["longitude"].iloc[0]],
                        mode='markers',
                        marker=dict(
                            size=0,
                            opacity=0,
                            color=[min(raw_values), max(raw_values)],
                            colorscale='jet',
                            showscale=True,
                            colorbar=colorbar_style),
                        # name="scale",
                        # hoverinfo='skip',
                        uid=f"pts_{point_attr}_colorbar"))
 
                else:
                    # Existing categorical logic
                    clean_series = display_df[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
 
                    for val in clean_fs:
                        # Filter the dataframe for JUST this specific value
                        mask = (clean_series == val)
                        sub_df = display_df[mask]
                       
                        if sub_df.empty:
                            continue
                           
                        # Get the specific color for this value from your color_map
                        trace_color = color_map.get(val, 'grey')
 
                        # 3. Add a unique trace for every single filter/category
                        fig.add_trace(go.Scattermap(
                            lat=sub_df["latitude"],
                            lon=sub_df["longitude"],
                            mode='markers',
                            marker=dict(
                                size=14,
                                opacity=0.8,
                                color=trace_color,),
                            name=val,
                            # Unique UID helps Plotly manage transitions
                            uid=f"pts_{point_attr}_{val}",
                            # showlegend=True
                            showlegend=False,
                        ))
                    pass
            else:
                print("Debug: No points match current filters.")
               
        # --- Add Boreholes ---
        if self.settings.show_boreholes and boreholes:
            # 'boreholes' here is now the 'bh_projections' list from your other script
            bh_list = boreholes if isinstance(boreholes, list) else [boreholes]
           
            # Extract values from the pre-calculated keys
            bh_lons = [bh['map_lon'] for bh in boreholes] # if 'map_lon' in bh]
            bh_lats = [bh['map_lat'] for bh in boreholes] # if 'map_lat' in bh]
            bh_names= [bh['id'] for bh in boreholes] # if 'map_lon' in bh]
 
            if bh_lons:
                fig.add_trace(go.Scattermap(
                    lat=bh_lats,
                    lon=bh_lons,
                    mode='markers+text',
                    marker=dict(size=14, color=self.settings.bh_color, symbol='circle'),
                    text=bh_names,
                    textposition="top right",
                    name="Boreholes",
                    showlegend=False,
                    below='',
                ))
 
        # --- Highlight ---
        # if self.highlighted is not None and show_points:
        #     df_h = self.dataframe.loc[[self.highlighted]]
        #     hfig = px.scatter_map(df_h, lat="latitude", lon="longitude")
        #     hfig.update_traces(marker=dict(size=20, color=self.settings.highlight_color), showlegend=False)
        #     for tr in hfig.data:
        #         fig.add_trace(tr)
 
        final_lines = final_line or []
        preview_line = preview_line or []
 
        for i, line_coords in enumerate(final_lines):
            # line_coords is now a list like [[lon1, lat1], [lon2, lat2], [lon3, lat3]...]
            if not isinstance(line_coords, (list, tuple)) or len(line_coords) < 2:
                continue
 
            # Extract all lons and lats for the polyline
            lons = [p[0] for p in line_coords]
            lats = [p[1] for p in line_coords]
 
            # Highlight selected line in Red, others in Yellow (or your line_color variable)
            is_selected = (i == selected_idx)
            color = "red" if is_selected else "yellow"
            width = 8 if is_selected else 4
 
            fig.add_trace(
                go.Scattermap( # or go.Scattermap depending on your version
                    lon=lons,
                    lat=lats,
                    mode="lines+markers" if is_selected else "lines", # Markers help see vertices
                    line=dict(color=color, width=width),
                    marker=dict(size=6, color=color) if is_selected else None,
                    below='',
                    name=f"Profile {i+1}",
                    showlegend=False,
                    hoverinfo="name"
                )
            )
 
        # Add the "Live" Hover Marker
        if hover_pt is not None and isinstance(hover_pt, list):
            fig.add_trace(go.Scattermap(
                lon=[hover_pt[0]],
                lat=[hover_pt[1]],
                mode="markers+text",
                marker=dict(size=15, color="cyan", symbol="circle", opacity=1),
                showlegend=False))
       
        fig.update_layout(
                        map=dict(
                            center=center,
                            zoom=zoom,
                            style="white-bg", # Ensure style is set here
                            layers=self._build_map_layers(show_google, show_tiff, show_png, google_op, tiff_op, png_op)),
                        margin=dict(r=0, t=0, l=0, b=0),
                        modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
                        # uirevision=f"{kwargs.get('uirevision')}_{point_attr}'",
                        uirevision="keep",
                        dragmode='pan')
        return fig
   
    def initialize(self, initial_rasters=None):
        if initial_rasters is None:
            initial_rasters = getattr(self, "initial_rasters", [])
 
        # Optional: default layers/opacity so loaded rasters are ON by default
        default_layers = ["google", "points"]
        default_opacity = {"google": 1.0}
        for r in initial_rasters:
            default_opacity[r["id"]] = r.get("default_opacity", 0.6)

        return html.Div([
            # --- HIDDEN UTILITIES (Triggers & Stores) ---
            # Moving these to the top ensures they exist before any callbacks fire
            html.Div("trigger",id="dummy-output", style={"display": "none"}),
            html.Div(id="test-display"),
            # --- show a message to the user if line drawn without zoom in---
            dcc.ConfirmDialog(
                    id='zoom-warning-dialog',
                    message='⛔ Drawing Error: Please zoom or pan the map once to initialize the coordinate system before drawing.',
                            ),
            # --- STORES ---
            dcc.Store(id="raster-load-trigger", data=0),
            dcc.Store(id="raster-busy-store", data=False),                      
            dcc.Store(id="raster-registry-store", data=initial_rasters),      # list of loaded rasters
            dcc.Store(id="layers-store", data=default_layers),  # sensible defaults
            dcc.Store(id="opacity-store", data = default_opacity),
                   
                    # ---- TOP CONTROL BAR ----
                    html.Div(
                        style={
                            "display": "flex",
                            "gap": "10px",
                            "position": "absolute",
                            "top": "10px",
                            "left": "10px",
                            "zIndex": 4000,
                            "alignItems": "flex-start"
                        },
                        children=[
                            # --- Layers Button ---
                            html.Div(
                                style={"position": "relative"},
                                children=[  
                                    html.Button("Layers ▼", id="layers-toggle", style={"padding": "5px 10px"}),
                                    html.Div(
                                        id="layers-panel",
                                        style={
                                            "display": "none",
                                            "position": "absolute",
                                            "background": "white",
                                            "padding": "10px",
                                            "marginTop": "6px",
                                            "borderRadius": "6px",
                                            "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
                                            "width": "220px",
                                        },
                                        children=[
                                            layer_row("Google", "google", checked=True, default_opacity=1),

                                            html.Div(id="dynamic-raster-layer-rows"),
                                           
                                            html.Div([
                                                html.Label("Borehole Data:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
                                                dcc.Checklist(
                                                    id={'type': 'layer-check', 'layer': 'boreholes'},
                                                    options=[{'label': ' Show Boreholes', 'value': 'on'}],
                                                    value=[],
                                                    style={'marginBottom': '15px'}
                                                )
                                            ], id='borehole-toggle-container', style={'display': 'block'} # if (bh_data and len(bh_data) > 0) else {'none'}
                                            ),
                                            html.Div([
                                                layer_row("Points", "points", checked=True, default_opacity=1),
                                                html.Div(
                                                    id="points-submenu-container",
                                                    children=[
                                                        html.Label("Attribute:", style={"fontWeight": "bold", "fontSize": "11px"}),
                                                        dcc.Dropdown(id="points-attr", clearable=False, 
                                                                    options=[], # Start empty
                                                                    value=None, 
                                                                    style={"marginBottom": "10px", "color": "black"}),
                                                        html.Label("Filter:", style={"fontWeight": "bold", "fontSize": "11px"}),
                                                        dcc.Checklist(
                                                            id="points-filter",
                                                                    options=[], # Start empty
                                                                    value=[], 
                                                            style={"maxHeight": "150px", "overflowY": "auto", "border": "1px solid #f9f9f9"},
                                                        ),
                                                        dcc.Store(id="points-color-map-store", data={}),
                                                        dcc.Store(id="points-filters-by-attr-store", data={}),
                                                    ],
                                                    style={"paddingLeft": "25px", "marginTop": "5px", "fontSize": "12px", "borderLeft": "2px solid #eee"},
                                                ),
                                            ]),
                                        ],
                                    ),
                                ],
                            ),
                      
                        
                        ],
                    ),                  
                   
                    # ---- MAIN CONTENT ROW: MAP (left) ----
                    html.Div(
                        style={
                            "position": "absolute",
                            "top": "70px",      # start below the toolbar
                            "left": "0",
                            "right": "0",
                            "bottom": "0",             # fill to bottom of screen
                            "display": "flex",
                            "gap": "10px",
                            "padding": "10px",
                            "boxSizing": "border-box",
                            "minHeight": 0,            # important for flex + Graph height
                        },
                        children=[
                            # ================= LEFT: MAP =================
                            html.Div(
                                id="map-wrapper",
                                style={
                                    "flex": "1",
                                    "position": "relative",
                                    "minHeight": 0,
                                    "borderRadius": "8px",
                                    "overflow": "hidden",
                                },
                                children=[
                                    dcc.Graph(
                                        figure=self.render(),
                                        id='gis',
                                        style={"height": "100%", "width": "100%"},
                                        config={"scrollZoom": True},
                                    ),
                                    html.Div(
                                        id="raster-busy-overlay",
                                        children="Waiting for .tiff cache...",
                                        style={
                                            "display": "none",
                                            "position": "absolute",
                                            "top": "12px",
                                            "right": "12px",
                                            "padding": "6px 10px",
                                            "background": "rgba(0,0,0,0.75)",
                                            "color": "white",
                                            "borderRadius": "6px",
                                            "zIndex": 999999,
                                            "fontSize": "12px",
                                            "pointerEvents": "none",
                                        },
                                    ),
                                ],
                            ),           
                        ],
                    ), 
                    gear_maker(self.id)])