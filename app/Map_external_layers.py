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
import time

import matplotlib.cm as cm
import matplotlib.colors as mcolors

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH

import dash_bootstrap_components as dbc

from scipy.spatial import cKDTree
from pyproj import Geod

from basepanel import Panel, gear_maker, dcc
from temframe import TEMframe
from Sections_plotting import *

# -------------------------
# Helpers for Layers
# -------------------------
def make_safe_id_from_stem(stem: str, prefix: str) -> str:
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", stem)
    return f"{prefix}_{stem}"

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
class ScatterMapRenderer_A(Panel):
    # def __init__(self, dataframe, settings, 
    #              highlighted=None,tiff_path=None,png_path=None,
    #              ):
        
    #     self.id = 'gis'
    #     self.dataframe = dataframe

    #     if self.dataframe is None: return self.empty_render()
    #     self.settings = settings
    #     self.highlighted = highlighted

    #     self._tiff_cache = {}  # {path: tiff_info}
    #     self._png_cache = {}   # {path: png_info}

    #     self.tiff_path = tiff_path
    #     self.png_path = png_path

    #     self.tiff_info = self._load_tiff() if tiff_path else None
    #     self.png_info = self._load_png() if png_path else None

    #     if self.tiff_info and self.png_info:
    #         self._check_bounds_match()  

    # -------------------------
    # Helpers for Layers
    # -------------------------
    @staticmethod
    def _needs_update(out_path: str, in_path: str) -> bool:
        """Return True if out_path missing OR older than in_path."""
        return (not os.path.exists(out_path)) or (os.path.getmtime(out_path) < os.path.getmtime(in_path))

    @staticmethod
    def _is_cache_dir(path: str) -> bool:
        """True if this path is the cache folder name."""
        return os.path.basename(path).lower() == ".raster_cache"

    @staticmethod
    def _is_derived_name(stem: str) -> bool:
        """Skip derived artifacts like *_wgs84.*."""
        s = stem.lower()
        return s.endswith("_wgs84") or "_wgs84" in s

    @staticmethod
    def _get_raster_cache_dir_for(src_path: str) -> str:
        """
        Create (if needed) a .raster_cache folder next to the source raster.
        """
        parent_dir = os.path.dirname(os.path.abspath(src_path))
        cache_dir = os.path.join(parent_dir, ".raster_cache")
        os.makedirs(cache_dir, exist_ok=True)
        return cache_dir
    
    # -------------------------
    # Folder scanning (registry)
    # -------------------------
    @staticmethod
    def build_raster_registry_from_folder(folder: str, include_subfolders: bool = False, require_pgw_for_png: bool = True):
        """
        Returns a list of raster dicts:
          [{"id","kind","name","path","default_opacity"}, ...]

        - Skips .raster_cache and derived *_wgs84.* files to avoid ingestion loops.
        - For PNGs, (optionally) requires a matching .pgw world file.

        Parameters
        ----------
        folder : str
            Folder to scan.
        include_subfolders : bool
            Whether to scan recursively.
        require_pgw_for_png : bool
            If True, skip PNGs missing a .pgw.
        """
        if not folder or not os.path.isdir(folder):
            return []

        exts = {".tif", ".tiff", ".png"}
        rasters = []

        walker = os.walk(folder) if include_subfolders else [(folder, [], os.listdir(folder))]

        for root, _, files in walker:
            # Skip cache folders entirely
            if ScatterMapRenderer._is_cache_dir(root):
                continue

            for fn in files:
                ext = os.path.splitext(fn)[1].lower()
                if ext not in exts:
                    continue

                stem = os.path.splitext(fn)[0]
                # Skip derived artifacts
                if ScatterMapRenderer._is_derived_name(stem):
                    continue

                path = os.path.join(root, fn)

                if ext in {".tif", ".tiff"}:
                    rasters.append({
                        "id": make_safe_id_from_stem(stem, "tiff"),
                        "kind": "tiff",
                        "name": fn,
                        "path": path,
                        "default_opacity": 0.6,
                    })

                elif ext == ".png":
                    pgw = os.path.splitext(path)[0] + ".pgw"
                    if require_pgw_for_png and (not os.path.exists(pgw)):
                        # skip non-georeferenced pngs
                        continue

                    rasters.append({
                        "id": make_safe_id_from_stem(stem, "png"),
                        "kind": "png",
                        "name": fn,
                        "path": path,
                        "default_opacity": 0.6,
                    })

        rasters.sort(key=lambda r: (r["kind"], r["name"].lower()))
        return rasters
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
    # TIFF loading with cache + derived outputs in .raster_cache
    def _load_tiff(self):
        """
        Loads self.tiff_path as a map overlay:
          - Reprojects to WGS84 (writes into .raster_cache next to source)
          - Renders a PNG (writes into same cache)
          - Returns {"image": <data-uri>, "bounds": (l,b,r,t), "png_path": ..., "reproj_path": ...}

        Uses:
          - in-memory cache keyed by (abs_src_path, src_mtime) to avoid repeated work
          - file timestamp checks to avoid reproject/re-render unless source changed
        """
        if not self.tiff_path:
            return None

        # Ensure cache dict exists
        if not hasattr(self, "_tiff_info_cache"):
            self._tiff_info_cache = {}

        src = os.path.abspath(self.tiff_path)
        if not os.path.exists(src):
            raise FileNotFoundError(f"TIFF not found: {src}")

        src_mtime = os.path.getmtime(src)
        cache_key = (src, src_mtime)

        # ---- 0) in-memory cache (fastest) ----
        if cache_key in self._tiff_info_cache:
            return self._tiff_info_cache[cache_key]

        # ---- 1) derived paths in .raster_cache ----
        base = os.path.splitext(os.path.basename(src))[0]
        ext = os.path.splitext(src)[1].lower()  # keep .tif or .tiff

        cache_dir = self._get_raster_cache_dir_for(src)
        reproj = os.path.join(cache_dir, f"{base}_wgs84{ext}")
        png = os.path.join(cache_dir, f"{base}_wgs84.png")

        # ---- 2) reproject only if needed ----
        if self._needs_update(reproj, src):
            # Your existing function should write reproj
            self._reproject_to_wgs84(src, reproj)

        # ---- 3) render png only if needed ----
        with rasterio.open(reproj) as ds:
            bounds = ds.bounds

            if self._needs_update(png, reproj):
                # Read bands
                if ds.count >= 3:
                    img = reshape_as_image(ds.read([1, 2, 3]))
                else:
                    img = ds.read(1)

                lat_range = bounds.top - bounds.bottom
                lon_range = bounds.right - bounds.left
                aspect_ratio = lon_range / lat_range if lat_range != 0 else 1.0

                plt.figure(figsize=(100 * aspect_ratio, 100), dpi=100, facecolor="white")
                plt.imshow(img, origin="upper")
                plt.axis("off")
                plt.savefig(png, bbox_inches="tight", pad_inches=0, facecolor="white")
                plt.close()

        info = {
            "image": self._image_to_data_uri(png),
            "bounds": (bounds.left, bounds.bottom, bounds.right, bounds.top),
            "png_path": png,
            "reproj_path": reproj,
        }

        self._tiff_info_cache[cache_key] = info
        return info

    def get_tiff_info(self, path):
        if not path:
            return None
        path = os.path.abspath(path)

        if path in self._tiff_cache:
            return self._tiff_cache[path]

        # Load once
        self.tiff_path = path  # only if your _load_tiff uses self.tiff_path
        info = self._load_tiff()
        self._tiff_cache[path] = info
        return info

    def get_png_info(self, path):
        if not path:
            return None
        path = os.path.abspath(path)

        if path in self._png_cache:
            return self._png_cache[path]

        self.png_path = path
        info = self._load_png()
        self._png_cache[path] = info
        return info

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

        # print("\n--- BOUNDS CHECK (WGS84) ---")
        # print(f"TIFF bounds: lon [{lt:.6f}, {rt:.6f}], lat [{bt:.6f}, {tt:.6f}]")
        # print(f" PNG bounds: lon [{lp:.6f}, {rp:.6f}], lat [{bp:.6f}, {tp:.6f}]")

        lon_overlap = not (rp < lt or lp > rt)
        lat_overlap = not (tp < bt or bp > tt)

        # print(f"Longitude overlap: {lon_overlap}")
        # print(f" Latitude overlap: {lat_overlap}")

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
        # print("MAP LAYERS:", len(layers))
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
    # def render(self, show_google=True ,show_tiff=True, show_png=True, show_points=True, show_boreholes=True, boreholes=None,
    #            google_op=1, tiff_op=0.6, png_op=0.6, line_color='yellow', view=None, 
    #            preview_line=None, final_line=None, selected_idx=None, hover_pt=None, 
    #            point_attr=None, point_filters=None, color_map=None, **kwargs):
        
    #     fig = go.Figure()
    #     if point_attr is None:
    #             point_attr = "none"

    #    # --- Decide zoom & center ---
    #     zoom = view.get("zoom") if view and "zoom" in view else self.settings.zoom
    #     self.settings.zoom=zoom

    #     center = view.get("center") if view and "center" in view else self._compute_df_center()
        
    #     # figure without the points to keep the map on when all points are off
        
    #     fig = px.scatter_map(
    #         self.dataframe.iloc[0:0],  # empty base
    #         lat="latitude",
    #         lon="longitude",
    #         color=None,
    #         zoom=zoom,
    #         center=center,)
        
    #     fig.update_layout(
    #             map=dict(center=center,zoom=zoom),
    #             showlegend=False,)

    #     # if self.dataframe is None or self.dataframe.empty:
    #     #     return None
    #     is_numeric = False
        
    #     if point_filters is None:
    #         point_filters = kwargs.get('point_filters', [])
            
    #     if point_attr is None:
    #         point_attr = kwargs.get('point_attr', 'date')
        
    #     if show_points and self.dataframe is not None:
    #         display_df = pd.DataFrame() # Default to empty

    #         if point_attr in self.dataframe.columns and point_filters:
    #             # Normalize column: string -> no .0 -> stripped
    #             col_str = self.dataframe[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
                
    #             # Normalize filters: list of strings -> no .0 -> stripped
    #             if not isinstance(point_filters, list):
    #                 point_filters = [point_filters]
    #             clean_fs = [str(f).replace('.0', '').strip() for f in point_filters]
                
    #             # FILTER: Get rows where column is in our list of clean filters
    #             display_df = self.dataframe[col_str.isin(clean_fs)]
                    
    #         # Debug inside renderer
    #         # print(f"RENDERER: Found {len(display_df)} points for {point_attr}")

    #         if not display_df.empty:
    #             # Check if it's one of our numeric columns
    #             numeric_cols = ['elevation', 'daytime', 'Data Residual', 'DOI']
    #             is_numeric = point_attr in numeric_cols

    #             if is_numeric:
    #                 raw_values = pd.to_numeric(display_df[point_attr], errors='coerce').tolist()
    #                 hex_colors = get_numeric_colors(raw_values, cmap_name='jet')
                    
    #                 # 1. Main Trace (The actual dots)
    #                 fig.add_trace(go.Scattermap(
    #                     lat=display_df["latitude"],
    #                     lon=display_df["longitude"],
    #                     customdata=display_df.index,# for the model plots
    #                     mode='markers',
    #                     marker=dict(size=14, opacity=0.8, color=hex_colors), # PURE HEX
    #                     # name=point_attr,
    #                     showlegend=True,
    #                     uid=f"pts_{point_attr}_dots"))
                    
    #                 # to remove the trace 1 text
    #                 fig.update_layout(hoverlabel=dict(namelength=0),)

    #                 # 2. Dummy Trace (Just for the Colorbar)
    #                 # We put one point at the first location but make it invisible (size 0)
    #                 colorbar_style = dict(
    #                     title=dict(
    #                         text=point_attr, 
    #                         font = dict(color="black", size=14, family="Arial Black"),
    #                         side ="top",  # This is the replacement for 'titleside'
    #                         ),
    #                     thickness=20,
    #                     x=1.02,           # Move to the right of the map
    #                     xanchor="center",   
    #                     tickfont=dict(color="black", size=11),
    #                     # White background styling
    #                     bgcolor="rgba(255, 255, 255, 0.9)", 
    #                     outlinecolor="white",               
    #                     outlinewidth=2,
    #                     len=0.6,          # Makes the bar a bit shorter/neater
    #                     yanchor="middle",
    #                     y=0.5             # Centers it vertically
    #                 )

    #                 fig.add_trace(go.Scattermap(
    #                     lat=[display_df["latitude"].iloc[0]],
    #                     lon=[display_df["longitude"].iloc[0]],
    #                     mode='markers',
    #                     marker=dict(
    #                         size=0, 
    #                         opacity=0,
    #                         color=[min(raw_values), max(raw_values)], 
    #                         colorscale='jet',
    #                         showscale=True,
    #                         colorbar=colorbar_style),
    #                     # name="scale",
    #                     # hoverinfo='skip',
    #                     uid=f"pts_{point_attr}_colorbar"))

    #             else:
    #                 # Existing categorical logic
    #                 clean_series = display_df[point_attr].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    #                 for val in clean_fs:
    #                     # Filter the dataframe for JUST this specific value
    #                     mask = (clean_series == val)
    #                     sub_df = display_df[mask]
                        
    #                     if sub_df.empty:
    #                         continue
                            
    #                     # Get the specific color for this value from your color_map
    #                     trace_color = color_map.get(val, 'grey')

    #                     # 3. Add a unique trace for every single filter/category
    #                     fig.add_trace(go.Scattermap(
    #                         lat=sub_df["latitude"],
    #                         lon=sub_df["longitude"],
    #                         mode='markers',
    #                         marker=dict(
    #                             size=14,
    #                             opacity=0.8,
    #                             color=trace_color,),
    #                         name=val, 
    #                         # Unique UID helps Plotly manage transitions
    #                         uid=f"pts_{point_attr}_{val}",
    #                         showlegend=True
    #                     ))
    #                 pass
    #         else:
    #             print("Debug: No points match current filters.")
                
    #     # --- Add Boreholes ---
    #     if show_boreholes and boreholes:
    #         # 'boreholes' here is now the 'bh_projections' list from your other script
    #         bh_list = boreholes if isinstance(boreholes, list) else [boreholes]
            
    #         # Extract values from the pre-calculated keys
    #         bh_lons = [bh['map_lon'] for bh in boreholes] # if 'map_lon' in bh]
    #         bh_lats = [bh['map_lat'] for bh in boreholes] # if 'map_lat' in bh]
    #         bh_names = [bh['id'] for bh in boreholes] # if 'map_lon' in bh]

    #         if bh_lons:
    #             fig.add_trace(go.Scattermap(
    #                 lat=bh_lats,
    #                 lon=bh_lons,
    #                 mode='markers+text',
    #                 marker=dict(size=14, color=settings.bh_color, symbol='circle'),
    #                 text=bh_names,
    #                 textposition="top right",
    #                 name="Boreholes",
    #                 showlegend=False,
    #                 below='',
    #             ))

    #     # --- Highlight ---
    #     if self.highlighted is not None and show_points:
    #         df_h = self.dataframe.loc[[self.highlighted]]
    #         hfig = px.scatter_map(df_h, lat="latitude", lon="longitude")
    #         hfig.update_traces(marker=dict(size=20, color=self.settings.highlight_color), showlegend=False)
    #         for tr in hfig.data:
    #             fig.add_trace(tr)

    #     final_lines = final_line or []
    #     preview_line = preview_line or []

    #     for i, line_coords in enumerate(final_lines):
    #         # line_coords is now a list like [[lon1, lat1], [lon2, lat2], [lon3, lat3]...]
    #         if not isinstance(line_coords, (list, tuple)) or len(line_coords) < 2:
    #             continue

    #         # Extract all lons and lats for the polyline
    #         lons = [p[0] for p in line_coords]
    #         lats = [p[1] for p in line_coords]

    #         # Highlight selected line in Red, others in Yellow (or your line_color variable)
    #         is_selected = (i == selected_idx)
    #         color = "red" if is_selected else "yellow"
    #         width = 8 if is_selected else 4

    #         fig.add_trace(
    #             go.Scattermap( # or go.Scattermap depending on your version
    #                 lon=lons,
    #                 lat=lats,
    #                 mode="lines+markers" if is_selected else "lines", # Markers help see vertices
    #                 line=dict(color=color, width=width),
    #                 marker=dict(size=6, color=color) if is_selected else None,
    #                 below='',
    #                 name=f"Profile {i+1}",
    #                 showlegend=False,
    #                 hoverinfo="name"
    #             )
    #         )

    #     # Add the "Live" Hover Marker
    #     if hover_pt is not None and isinstance(hover_pt, list):
    #         fig.add_trace(go.Scattermap(
    #             lon=[hover_pt[0]],
    #             lat=[hover_pt[1]],
    #             mode="markers+text",
    #             marker=dict(size=15, color="cyan", symbol="circle", opacity=1),
    #             showlegend=False))
        
    #     fig.update_layout(
    #                     map=dict(
    #                         center=center, 
    #                         zoom=zoom,
    #                         style="white-bg", # Ensure style is set here
    #                         layers=self._build_map_layers(show_google, show_tiff, show_png, google_op, tiff_op, png_op)),
    #                     margin=dict(r=0, t=0, l=0, b=0),
    #                     modebar=dict(add=['drawline', 'drawopenpath', 'eraseshape'], remove=['zoomIn', 'zoomOut']),
    #                     # uirevision=f"{kwargs.get('uirevision')}_{point_attr}'",
    #                     uirevision="keep",
    #                     dragmode='pan')
    #     return fig

   
    # def initialize(self, initial_rasters=None):
    #     if initial_rasters is None:
    #         initial_rasters = getattr(self, "initial_rasters", [])

    #     # Optional: default layers/opacity so loaded rasters are ON by default
    #     default_layers = ["google", "points"] 
    #     default_opacity = {"google": 1.0}
    #     for r in initial_rasters:
    #         default_opacity[r["id"]] = r.get("default_opacity", 0.6)
        
    #     return html.Div([
    #         # --- HIDDEN UTILITIES (Triggers & Stores) ---
    #         # Moving these to the top ensures they exist before any callbacks fire
    #         html.Div("trigger",id="dummy-output", style={"display": "none"}),
    #         html.Div(id="test-display"),
    #         # --- for ctrl + alt + left click and show models  ---
    #         html.Div(id="window-container", style={"position": "relative", "zIndex": 9999}),
    #         dcc.Store(id="combined-window-store", data={"window_id": None, "indices": []}),            
    #         dcc.Store(id="right-click-index-store", data=None),
    #         dcc.Store(id='active-windows-store', data=[]),
    #         # --- show a message to the user if line drawn without zoom in---
    #         dcc.ConfirmDialog(
    #                             id='zoom-warning-dialog',
    #                             message='⛔ Drawing Error: Please zoom or pan the map once to initialize the coordinate system before drawing.',
    #                         ),
    #         # --- STORES ---
    #         dcc.Store(id="raster-load-trigger", data=0),
    #         dcc.Store(id="raster-busy-store", data=False),                       
    #         dcc.Store(id="raster-registry-store", data=initial_rasters),      # list of loaded rasters
    #         dcc.Store(id="layers-store", data=default_layers),  # sensible defaults

    #         dcc.Store(id="opacity-store", data = default_opacity),
    #         dcc.Store(id="line-preview-store"),
    #         dcc.Store(id="line-final-store"),
    #         dcc.Store(id="section-mode-store", data="blocky"),
    #         dcc.Store(id="map-view-store"),
    #         dcc.Store(id="selected-line-index", data=0),
    #         dcc.Store(id="map-hover-marker-store", data=None),
    #         dcc.Store(id="map-settings-store", data={}), # plot_attribute': 'date', 'color': '#ff0000'
    #         dcc.Store(id='global-color-map-store', data=color_master_map),
    #         dcc.Store(id="points-available-attrs-store", data=existing_attrs),

    #         # dcc.Store(id="profile-busy-store", data=False),
    #         dcc.Store(id="profile-busy-store", data=False),
    #         dcc.Store(id="profile-load-trigger", data=0),
    #         dcc.Store(id="profile-last-sig", data=None),  # used to detect changes

    #         # --- MAIN UI CONTAINER ---
    #         html.Div(
    #             id=self.id,
    #             style={"height": "100vh", "position": "relative", "fontFamily": "sans-serif"},
    #             children=[
                    
    #                 # ---- TOP CONTROL BAR ----
    #                 html.Div(
    #                     style={
    #                         "display": "flex", 
    #                         "gap": "10px", 
    #                         "position": "absolute", 
    #                         "top": "10px", 
    #                         "left": "10px", 
    #                         "zIndex": 4000,
    #                         "alignItems": "flex-start"
    #                     },
    #                     children=[
    #                         # --- Layers Button ---
    #                         html.Div(
    #                             style={"position": "relative"},
    #                             children=[  
    #                                 html.Button("Layers ▼", id="layers-toggle", style={"padding": "5px 10px"}),
    #                                 html.Div(
    #                                     id="layers-panel",
    #                                     style={
    #                                         "display": "none",
    #                                         "position": "absolute",
    #                                         "background": "white",
    #                                         "padding": "10px",
    #                                         "marginTop": "6px",
    #                                         "borderRadius": "6px",
    #                                         "boxShadow": "0 2px 8px rgba(0,0,0,0.3)",
    #                                         "width": "220px",
    #                                     },
    #                                     children=[
    #                                         layer_row("Google", "google", checked=True, default_opacity=1),
    #                                         # layer_row("TIFF", "tiff", default_opacity=0.6),
    #                                         # layer_row("PNG", "png", default_opacity=0.6),
    #                                         html.Div(id="dynamic-raster-layer-rows"),
                                            
    #                                         html.Div([
    #                                             html.Label("Borehole Data:", style={'fontWeight': 'bold', 'marginTop': '10px'}),
    #                                             dcc.Checklist(
    #                                                 id={'type': 'layer-check', 'layer': 'boreholes'}, 
    #                                                 options=[{'label': ' Show Boreholes', 'value': 'on'}],
    #                                                 value=[], 
    #                                                 style={'marginBottom': '15px'}
    #                                             )
    #                                         ], id='borehole-toggle-container', style={'display': 'block' if (bh_data and len(bh_data) > 0) else 'none'}
    #                                         ),
    #                                         html.Div([
    #                                             layer_row("Points", "points", checked=True, default_opacity=1),
    #                                             html.Div(
    #                                                 id="points-submenu-container",
    #                                                 children=[
    #                                                     html.Label("Attribute:", style={"fontWeight": "bold", "fontSize": "11px"}),
    #                                                     dcc.Dropdown(id="points-attr", clearable=False, style={"marginBottom": "10px", "color": "black"}),
    #                                                     html.Label("Filter:", style={"fontWeight": "bold", "fontSize": "11px"}),
    #                                                     dcc.Checklist(
    #                                                         id="points-filter",
    #                                                         style={"maxHeight": "150px", "overflowY": "auto", "border": "1px solid #f9f9f9"},
    #                                                     ),
    #                                                     dcc.Store(id="points-color-map-store", data={}),
    #                                                     dcc.Store(id="points-filters-by-attr-store", data={}),
    #                                                 ],
    #                                                 style={"paddingLeft": "25px", "marginTop": "5px", "fontSize": "12px", "borderLeft": "2px solid #eee"},
    #                                             ),
    #                                         ]),
    #                                     ],
    #                                 ),
    #                             ],
    #                         ),

    #                         # --- Section Mode Button ---
    #                         html.Div(
    #                             style={"position": "relative"},
    #                             children=[
    #                                 html.Button("Section ▼", id="section-toggle", style={"padding": "5px 10px"}),
    #                                 html.Div(
    #                                     id="section-panel",
    #                                     style={"display": "none", "position": "absolute", "background": "white", "padding": "8px", "borderRadius": "6px", "boxShadow": "0 2px 6px rgba(0,0,0,0.25)", "marginTop": "4px", "minWidth": "140px"},
    #                                     children=[
    #                                         html.Div("Interpolated", id={"type": "section-option", "mode": "interp"}, style={"padding": "6px", "cursor": "pointer"}),
    #                                         html.Div("Blocky", id={"type": "section-option", "mode": "blocky"}, style={"padding": "6px", "cursor": "pointer"}),
    #                                         html.Div("Combined", id={"type": "section-option", "mode": "combined"}, style={"padding": "6px", "cursor": "pointer"}),
    #                                     ],
    #                                 ),
    #                             ]
    #                         ),

    #                         # --- Lines Mode Button ---
    #                         html.Div(
    #                             style={"position": "relative"},
    #                             children=[
    #                                 html.Button("Lines ▼", id="profiles-toggle", style={"padding": "5px 10px"}),
    #                                 html.Div(
    #                                     id="profiles-panel",
    #                                     style={"display": "none", "position": "absolute", "background": "white", "padding": "12px", "marginTop": "6px", "borderRadius": "6px", "boxShadow": "0 2px 8px rgba(0,0,0,0.3)", "width": "280px"},
    #                                     children=[
    #                                         html.Div("Active Profiles", style={"fontWeight": "bold", "marginBottom": "8px", "fontSize": "13px"}),
    #                                         html.Div(id="profile-list-container", style={"maxHeight": "250px", "overflowY": "auto", "marginBottom": "10px", "border": "1px solid #eee", "borderRadius": "4px"}),
    #                                         html.Hr(style={"margin": "10px 0", "border": "0", "borderTop": "1px solid #eee"}),
    #                                         html.Div(
    #                                             style={"display": "flex", "gap": "8px"},
    #                                             children=[
    #                                                 html.Button("Clear Selected", id="clear-selected-btn", style={"fontSize": "11px", "flex": 1, "padding": "5px", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}),
    #                                                 html.Button("Clear All", id="clear-all-btn", style={"fontSize": "11px", "flex": 1, "padding": "5px", "color": "red", "backgroundColor": "#fff5f5", "border": "1px solid #ffcccc", "cursor": "pointer"}),
    #                                             ]
    #                                         )
    #                                     ]
    #                                 ),
    #                             ]
    #                         ),
    #                     ],
    #                 ),                  
                    
    #                 # ---- MAIN CONTENT ROW: MAP (left) + PROFILE (right) ----
    #                 html.Div(
    #                     style={
    #                         "position": "absolute",
    #                         "top": "70px",      # start below the toolbar
    #                         "left": "0",
    #                         "right": "0",
    #                         "bottom": "0",             # fill to bottom of screen
    #                         "display": "flex",
    #                         "gap": "10px",
    #                         "padding": "10px",
    #                         "boxSizing": "border-box",
    #                         "minHeight": 0,            # important for flex + Graph height
    #                     },
    #                     children=[
    #                         # ================= LEFT: MAP =================
    #                         html.Div(
    #                             id="map-wrapper",
    #                             style={
    #                                 "flex": "1",
    #                                 "position": "relative",
    #                                 "minHeight": 0,
    #                                 "borderRadius": "8px",
    #                                 "overflow": "hidden",
    #                             },
    #                             children=[
    #                                 dcc.Graph(
    #                                     figure=self.render(),
    #                                     id=self.id,
    #                                     style={"height": "100%", "width": "100%"},
    #                                     config={"scrollZoom": True},
    #                                 ),
    #                                 html.Div(
    #                                     id="raster-busy-overlay",
    #                                     children="Waiting for .tiff cache...",
    #                                     style={
    #                                         "display": "none",
    #                                         "position": "absolute",
    #                                         "top": "12px",
    #                                         "right": "12px",
    #                                         "padding": "6px 10px",
    #                                         "background": "rgba(0,0,0,0.75)",
    #                                         "color": "white",
    #                                         "borderRadius": "6px",
    #                                         "zIndex": 999999,
    #                                         "fontSize": "12px",
    #                                         "pointerEvents": "none",
    #                                     },
    #                                 ),
    #                             ],
    #                         ),

    #                         # ================= RIGHT: PROFILE =================
                        
    #                        html.Div(
    #                                 id="profile-plot-container",
    #                                 style={
    #                                     "flex": "1", "position": "relative", "minHeight": 0,
    #                                     "background": "white", "borderRadius": "8px",
    #                                     "boxShadow": "0 0 10px rgba(0,0,0,0.15)", "padding": "5px",
    #                                     "display": "flex", "flexDirection": "column", "overflow": "hidden",
    #                                 },
    #                                 children=[
    #                                     # 1. THE OVERLAY (Now outside the content div)
    #                                     html.Div(
    #                                         "Preparing profile...",
    #                                         id="profile-busy-overlay",
    #                                         style={
    #                                             "display": "none", # Hidden by default
    #                                             "position": "absolute", "top": "120px", "left": "12px", "right": "auto",
    #                                             "padding": "6px 15px", "background": "rgba(0,0,0,0.8)",
    #                                             "color": "white", "zIndex": 9999, "borderRadius": "6px"
    #                                         }
    #                                     ),

    #                                     # 2. THE CONTENT AREA (This is what the callback targets)
    #                                     html.Div(
    #                                         id="profile-plot-content", 
    #                                         style=
    #                                         {"flex": "1",
    #                                         "width": "100%", "height": "100%",
    #                                         "justifyContent": "center",
    #                                         "alignItems": "center"},
    #                                         children=[dcc.Graph(id="profile-plot_main", #figure=go.Figure(),
    #                                                             figure={
    #                                                                     "data": [],
    #                                                                     "layout": {
    #                                                                         "plot_bgcolor": "red",
    #                                                                         "paper_bgcolor": "white",
    #                                                                         "template": "none",
    #                                                                         "xaxis": {"visible": False, "showgrid": False, "zeroline": False},
    #                                                                         "yaxis": {"visible": False, "showgrid": False, "zeroline": False},
    #                                                                         "margin": {"t": 0, "b": 0, "l": 0, "r": 0},
    #                                                                         "annotations": [{
    #                                                                             "text": "Select or draw a line to generate a profile",
    #                                                                             "showarrow": False,
    #                                                                             "font": {"size": 16, "color": "gray"}
    #                                                                         }]
    #                                                                     }
    #                                                                 },
    #                                                             style={ "height": "100%", "width": "100%", "background": "white", "borderRadius": "8px", "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)" }
    #                                                             )]
    #                                     )
    #                                 ]
    #                             )
                        
                        
    #                     ],
    #                 ),


    #                 gear_maker(self.id),
    #             ],
    #         )
    #     ])