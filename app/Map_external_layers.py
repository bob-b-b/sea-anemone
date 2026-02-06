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
class GIS_helpers(Panel):
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
    # @staticmethod
    # def build_raster_registry_from_folder(folder: str, include_subfolders: bool = False, require_pgw_for_png: bool = True):
    #     """
    #     Returns a list of raster dicts:
    #       [{"id","kind","name","path","default_opacity"}, ...]

    #     - Skips .raster_cache and derived *_wgs84.* files to avoid ingestion loops.
    #     - For PNGs, (optionally) requires a matching .pgw world file.

    #     Parameters
    #     ----------
    #     folder : str
    #         Folder to scan.
    #     include_subfolders : bool
    #         Whether to scan recursively.
    #     require_pgw_for_png : bool
    #         If True, skip PNGs missing a .pgw.
    #     """
    #     if not folder or not os.path.isdir(folder):
    #         return []

    #     exts = {".tif", ".tiff", ".png"}
    #     rasters = []

    #     walker = os.walk(folder) if include_subfolders else [(folder, [], os.listdir(folder))]

    #     for root, _, files in walker:
    #         # Skip cache folders entirely
    #         if ScatterMapRenderer._is_cache_dir(root):
    #             continue

    #         for fn in files:
    #             ext = os.path.splitext(fn)[1].lower()
    #             if ext not in exts:
    #                 continue

    #             stem = os.path.splitext(fn)[0]
    #             # Skip derived artifacts
    #             if ScatterMapRenderer._is_derived_name(stem):
    #                 continue

    #             path = os.path.join(root, fn)

    #             if ext in {".tif", ".tiff"}:
    #                 rasters.append({
    #                     "id": make_safe_id_from_stem(stem, "tiff"),
    #                     "kind": "tiff",
    #                     "name": fn,
    #                     "path": path,
    #                     "default_opacity": 0.6,
    #                 })

    #             elif ext == ".png":
    #                 pgw = os.path.splitext(path)[0] + ".pgw"
    #                 if require_pgw_for_png and (not os.path.exists(pgw)):
    #                     # skip non-georeferenced pngs
    #                     continue

    #                 rasters.append({
    #                     "id": make_safe_id_from_stem(stem, "png"),
    #                     "kind": "png",
    #                     "name": fn,
    #                     "path": path,
    #                     "default_opacity": 0.6,
    #                 })

    #     rasters.sort(key=lambda r: (r["kind"], r["name"].lower()))
    #     return rasters


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

        # if lon_overlap and lat_overlap:
        #     print("✅ Bounds OVERLAP correctly")
        # else:
        #     print("❌ Bounds DO NOT overlap")

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
  
    