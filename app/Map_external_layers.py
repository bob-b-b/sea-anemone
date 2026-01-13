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

import matplotlib.cm as cm
import matplotlib.colors as mcolors

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH
from scipy.spatial import cKDTree
from pyproj import Geod

from basepanel import Panel, gear_maker, dcc
from temframe import TEMframe



# --------------------- Settings ---------------------
class Settings:
    color = "red"
    highlight_color = "yellow"
    zoom = 10
    png_crs = "EPSG:32637"

# ------------------- Helper: Layers/Opacity Box -------------------
def layer_row(label, layer_id, checked=False, default_opacity=1.0):
        return html.Div(
            style={
                "display": "flex",
                "alignItems": "center",
                "gap": "6px",
                "position": "relative",
                "marginBottom": "6px",
            },
            children=[
                dcc.Checklist(
                    id={"type": "layer-check", "layer": layer_id},
                    options=[{"label": "", "value": "on"}],
                    value=["on"] if checked else [],
                    style={"margin": 0},
                ),
                html.Span(label, style={"flex": "1"}),

                html.Button(
                    "⋮",
                    id={"type": "layer-menu-btn", "layer": layer_id},
                    style={
                        "border": "none",
                        "background": "none",
                        "cursor": "pointer",
                        "fontSize": "16px",
                    },
                ),

                html.Div(
                    id={"type": "layer-menu", "layer": layer_id},
                    style={
                        "display": "none",
                        "position": "absolute",
                        "right": "0",
                        "top": "24px",
                        "background": "white",
                        "padding": "8px",
                        "borderRadius": "4px",
                        "boxShadow": "0 2px 6px rgba(0,0,0,0.25)",
                        "zIndex": 4000,
                        "width": "160px",
                    },
                    children=[
                        html.Label("Opacity"),
                        dcc.Slider(
                            id={"type": "layer-opacity", "layer": layer_id},
                            min=0, max=1, step=0.05,
                            value=default_opacity,
                            marks={0: "0", 0.5: "0.5", 1: "1"},
                        ),
                    ],
                ),
            ],
        )




    # ------------------------- double click line lat lon save as strings -------------------------
    

# --------------------- ScatterMapRenderer ---------------------
class ScatterMapRenderer(Panel):
    def __init__(self, 
                 dataframe, 
                 settings, 
                 highlighted=None,
                 tiff_path=None,
                 png_path=None,
                 ):
        
        self.dataframe = dataframe
        self.settings = settings
        self.highlighted = highlighted
        self.tiff_path = tiff_path
        self.png_path = png_path

        self.tiff_info = self._load_tiff() if tiff_path else None
        self.png_info = self._load_png() if png_path else None

        if self.tiff_info and self.png_info:
            self._check_bounds_match()  

    # ------------------- Helper: load PNG -------------------
    def _load_png(self):
        pgw = os.path.splitext(self.png_path)[0] + ".pgw"
        if not os.path.exists(pgw):
            raise ValueError("PNG requires PGW or manual bounds")

        if self.png_path.lower().endswith(".png"):
            bounds = self._read_world_file(self.png_path)

            # Fallback to manual bounds
            if bounds is None:
                if not hasattr(self.settings, "png_bounds"):
                    raise ValueError(
                        "PNG file has no world file. Please provide bounds in settings.png_bounds = (left, bottom, right, top)"
                    )
                bounds = self.settings.png_bounds

        if hasattr(self.settings, "png_crs"):
            bounds = self._reproject_bounds(bounds, self.settings.png_crs)

        return {
            "image": self._image_to_data_uri(self.png_path),
            "bounds": bounds,}

    # ------------------- Helper: load TIFF -------------------
    def _load_tiff(self):
        reproj = self.tiff_path.replace(".tiff", "_wgs84.tiff")
        tiff_path = self._reproject_to_wgs84(self.tiff_path, reproj)

        with rasterio.open(tiff_path) as ds:
            bounds = ds.bounds
            png = reproj.replace(".tiff", ".png")

            if not os.path.exists(png):
                  # Read bands
                if ds.count >= 3:
                    img = ds.read([1,2,3])
                    img = reshape_as_image(img)
                else:
                    img = ds.read(1)

                lat_range = bounds.top - bounds.bottom
                lon_range = bounds.right - bounds.left
                aspect_ratio = lon_range / lat_range

                plt.figure(figsize=(100 * aspect_ratio, 100), dpi=100)

                plt.figure(figsize=(100 * aspect_ratio, 100), facecolor="white")
                plt.imshow(img, origin="upper")
                plt.axis("off")
                plt.savefig(png, bbox_inches="tight", pad_inches=0, facecolor="white")
                plt.close()

        return {
            "image": self._image_to_data_uri(png),
            "bounds": (bounds.left, bounds.bottom, bounds.right, bounds.top),}
  
    # ------------------------- GEOREFERENCE & CONVERSION -------------------------
    def _reproject_to_wgs84(self, src_path, dst_path):
        """Reproject any CRS TIFF to EPSG:4326"""
        with rasterio.open(src_path) as src:
            if src.crs.to_epsg() == 4326:
                return src_path  # already WGS84

            transform, width, height = calculate_default_transform(
                src.crs, "EPSG:4326", src.width, src.height, *src.bounds)

            kwargs = src.meta.copy()
            kwargs.update({"crs": "EPSG:4326", "transform": transform,
                           "width": width, "height": height})

            with rasterio.open(dst_path, "w", **kwargs) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i),
                        destination=rasterio.band(dst, i),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=transform,
                        dst_crs="EPSG:4326",
                        resampling=Resampling.bilinear,)
        return dst_path

    def _reproject_bounds(self, bounds, src_crs):
        """Reproject bounds from src_crs to EPSG:4326"""
        left, bottom, right, top = bounds
        transformer = Transformer.from_crs(src_crs, "EPSG:4326", always_xy=True)
        lon_left, lat_bottom = transformer.transform(left, bottom)
        lon_right, lat_top = transformer.transform(right, top)
        # Ensure top > bottom
        if lat_top < lat_bottom:
            lat_top, lat_bottom = lat_bottom, lat_top
        return (lon_left, lat_bottom, lon_right, lat_top)

    def _image_to_data_uri(self, path):       
        with open(path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    # ------------------------- WORLD FILE HANDLING -------------------------
    def _read_world_file(self, png_path):
        """Read .pgw world file and return bounds in projected units"""
        world_file = os.path.splitext(png_path)[0] + ".pgw"
        if not os.path.exists(world_file):
            return None
        with open(world_file) as f:
            a = float(f.readline().strip())  # pixel width
            d = float(f.readline().strip())  # rotation x
            b = float(f.readline().strip())  # rotation y
            e = float(f.readline().strip())  # pixel height (usually negative)
            c = float(f.readline().strip())  # top-left X
            f_ = float(f.readline().strip()) # top-left Y

        img = Image.open(png_path)
        width, height = img.size

        left = c
        right = c + a * width
        if e < 0:
            top = f_
            bottom = f_ + e * height
        else:
            bottom = f_
            top = f_ + e * height

        # Ensure top > bottom
        if top < bottom:
            top, bottom = bottom, top

        return left, bottom, right, top

    # ------------------- Check bounds of png and Tiff -------------------
    def _check_bounds_match(self):
        if not self.tiff_info or not self.png_info:
            print("⚠️ One of the layers is missing – cannot compare bounds")
            return

        lt, bt, rt, tt = self.tiff_info["bounds"]
        lp, bp, rp, tp = self.png_info["bounds"]

        print("\n--- BOUNDS CHECK (WGS84) ---")
        print(f"TIFF bounds: lon [{lt:.6f}, {rt:.6f}], lat [{bt:.6f}, {tt:.6f}]")
        print(f" PNG bounds: lon [{lp:.6f}, {rp:.6f}], lat [{bp:.6f}, {tp:.6f}]")

        lon_overlap = not (rp < lt or lp > rt)
        lat_overlap = not (tp < bt or bp > tt)

        print(f"Longitude overlap: {lon_overlap}")
        print(f" Latitude overlap: {lat_overlap}")

        if lon_overlap and lat_overlap:
            print("✅ Bounds OVERLAP correctly")
        else:
            print("❌ Bounds DO NOT overlap")

    # ------------------- Map layers -------------------
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
        print("MAP LAYERS:", len(layers))
        return layers
    
    # ------------------- Estimate points' center -------------------
    def _compute_df_center(self):
        """Return dict(lat=..., lon=...) as the center of the dataframe points"""
        if self.dataframe is None or self.dataframe.empty:
            # fallback center (0,0)
            return dict(lat=0, lon=0)
        return dict(
            lat=self.dataframe["latitude"].mean(),
            lon=self.dataframe["longitude"].mean()
        )
  


    # ------------------------- Render figure -------------------------
    def render(self, show_google=True ,show_tiff=True, show_png=True, show_points=True, 
               google_op=1, tiff_op=0.6, png_op=0.6, line_color='yellow', view=None, 
               preview_line=None, final_line=None, selected_idx=None):
        
        if self.dataframe is None or self.dataframe.empty:
            return None
            # --- Decide zoom & center ---
        zoom = view.get("zoom") if view and "zoom" in view else self.settings.zoom
        center = view.get("center") if view and "center" in view else self._compute_df_center()
        
        # figure without the points
        fig = px.scatter_map(
            self.dataframe.iloc[0:0],  # empty base
            lat="latitude",
            lon="longitude",
            zoom=zoom,
            center=center,)
        
        # --- Build figure ---
        if show_points:
            fig = px.scatter_map(self.dataframe,lat="latitude",lon="longitude",zoom=zoom,center=center,)

            fig.update_traces(marker=dict(size=18, color=self.settings.color), showlegend=False)

        fig.update_layout(
            map_style="white-bg",
            map_layers=self._build_map_layers(show_google, show_tiff, show_png, google_op, tiff_op, png_op),
            coloraxis_showscale=False,
            uirevision="keep",
            margin=dict(r=0, t=0, l=0, b=0),
            
            modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
            # shapes=[],
            newshape=dict( line_color='cyan', line_width=3, ),
            dragmode='pan'
        )

        # --- Highlight ---
        if self.highlighted is not None and show_points:
            df_h = self.dataframe.loc[[self.highlighted]]
            hfig = px.scatter_map(df_h, lat="latitude", lon="longitude")
            hfig.update_traces(marker=dict(size=20, color=self.settings.highlight_color), showlegend=False)
            for tr in hfig.data:
                fig.add_trace(tr)
    
    
        # =====================================================
        #           DRAW ALL FINAL SAVED LINES
        # =====================================================

        final_lines = final_line or []
        preview_line = preview_line or []

        for i,line in enumerate(final_lines):
            if not isinstance(line, (list, tuple)) or len(line) != 2:
                continue
            p0, p1 = line

            # Highlight selected line in Red, others in Yellow
            color = "red" if i == selected_idx else line_color
            width = 10 if i == selected_idx else 6

            fig.add_trace(
                go.Scattermap(
                    lon=[p0[0], p1[0]],
                    lat=[p0[1], p1[1]],
                    mode="lines",
                    line=dict(color=color, width=width),
                    name=f"Line {i+1}",
                    showlegend=False,
                    # hoverinfo="none"
                )
            )

        return fig
    

    def initialize(self):
        return html.Div(id="dummy-output", style={"display": "none"}), html.Div(
            style={"height": "100vh", "position": "relative", "fontFamily": "sans-serif"},
            children=[
                # ---- STORES ----
                dcc.Store(id="layers-store"),
                dcc.Store(id="opacity-store"),
                dcc.Store(id="line-preview-store"),
                dcc.Store(id="line-final-store"),
                dcc.Store(id="section-mode-store", data="blocky"),
                dcc.Store(id="map-view-store"),
                dcc.Store(id="selected-line-index", data=0), # Tracks the 👁️ selection

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
                                        layer_row("TIFF", "tiff", default_opacity=0.6),
                                        layer_row("PNG", "png", default_opacity=0.6),
                                        layer_row("Points", "points", checked=True, default_opacity=1),
                                    ],
                                ),
                            ]
                        ),

                        # --- Section Mode Button ---
                        html.Div(
                            style={"position": "relative"},
                            children=[
                                html.Button("Section ▼", id="section-toggle", style={"padding": "5px 10px"}),
                                html.Div(
                                    id="section-panel",
                                    style={
                                        "display": "none",
                                        "position": "absolute",
                                        "background": "white",
                                        "padding": "8px",
                                        "borderRadius": "6px",
                                        "boxShadow": "0 2px 6px rgba(0,0,0,0.25)",
                                        "marginTop": "4px",
                                        "minWidth": "140px",
                                    },
                                    children=[
                                        html.Div("Interpolated", id={"type": "section-option", "mode": "interp"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                        html.Div("Blocky", id={"type": "section-option", "mode": "blocky"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                        html.Div("Combined", id={"type": "section-option", "mode": "combined"},
                                                style={"padding": "6px", "cursor": "pointer"}),
                                    ],
                                ),
                            ]
                        ),

                        # --- Profiles/Lines Dropdown Panel ---
                        html.Div(
                            style={"position": "relative"},
                            children=[
                                html.Button("Lines ▼", id="profiles-toggle", style={"padding": "5px 10px"}),
                                html.Div(
                                    id="profiles-panel",
                                    style={
                                        "display": "none", 
                                        "position": "absolute",
                                        "background": "white",
                                        "padding": "12px",
                                        "marginTop": "6px",
                                        "borderRadius": "6px",
                                        "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
                                        "width": "280px", # Increased slightly for icon spacing
                                    },
                                    children=[
                                        html.Div("Active Profiles", style={"fontWeight": "bold", "marginBottom": "8px", "fontSize": "13px"}),
                                        
                                        # This container is populated dynamically by the master_line_controller callback
                                        html.Div(
                                            id="profile-list-container",
                                            style={
                                                "maxHeight": "250px", 
                                                "overflowY": "auto", 
                                                "marginBottom": "10px",
                                                "border": "1px solid #eee",
                                                "borderRadius": "4px"
                                            }
                                        ),
                                        
                                        html.Hr(style={"margin": "10px 0", "border": "0", "borderTop": "1px solid #eee"}),
                                        
                                        # Action Buttons
                                        html.Div(
                                            style={"display": "flex", "gap": "8px"},
                                            children=[
                                                html.Button(
                                                    "Clear Selected", 
                                                    id="clear-selected-btn", 
                                                    style={"fontSize": "11px", "flex": 1, "padding": "5px", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}
                                                ),
                                                html.Button(
                                                    "Clear All", 
                                                    id="clear-all-btn", 
                                                    style={"fontSize": "11px", "flex": 1, "padding": "5px", "color": "red", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}
                                                ),
                                            ]
                                        )
                                    ]
                                ),
                            ]
                        ),
                    ],
                ),

                # ---- MAP ----
                dcc.Graph(
                    id=self.id,
                    style={"height": "100vh", "width": "100%"},
                    config={"scrollZoom": True,}
                ),

                # ---- PROFILE PLOT ----
                dcc.Graph(
                    id="profile-plot",
                    style={
                        "height": "250px",
                        "position": "absolute",
                        "bottom": "10px",
                        "left": "10px",
                        "right": "10px",
                        "zIndex": 2000,
                        "background": "white",
                        "borderRadius": "8px",
                        "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)"
                    },
                ),

                gear_maker(self.id),
            ],
        )