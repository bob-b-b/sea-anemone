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


@nosj
class ProfileSettings(PanelSettings):
    res_min: int = 1
    res_max: int = 300
    radius: int = 50 
    column_width: int = 60
    num_labels_colorbar: int = 4
    # raster_cache_dir: str = r"C:\Users\au679476\Downloads\test_for_map_pngs_tiffs\raster_cache"

class Profile(Panel):
    def __init__(self, dataframe, **kwargs):
                    
        settings = kwargs.pop('settings', ProfileSettings(id='profile_plot_main'))       
        super().__init__(id = 'profile_plot_main', settings=settings)
        self.dataframe = dataframe

        for key, value in kwargs.items():
            setattr(self, key, value)

    # def empty_figure(self, msg="No profile selected."):
    #     fig = go.Figure()
    #     fig.add_annotation(text=msg, showarrow=False, font=dict(size=16, color="gray"))
    #     # fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(t=0,b=0,l=0,r=0))
    #     return fig
    


    def get_figure(self, lines, mode, selected_idx, view):
        print("lines:", lines)
        print("Selected IDX:", selected_idx)
        print("mode", mode)
        
        # 1. Handle Empty State
        if not lines or len(lines) == 0:
            return self.empty_figure("Draw a line on the map to generate a profile.")

        # 2. Extract Data Context
        try:
            idx = selected_idx if selected_idx is not None else -1
            current_line = lines[idx]
        except (IndexError, TypeError):
            current_line = lines[-1]

        # 3. Pre-process Dataframe
        # Note: self.dataframe is passed during __init__
        df_up_map, color_master_map, existing_attrs = preprocess_new_df(self.dataframe)
        
        # 4. Gather Geometry Data
        y_depth = np.array(df_up_map["Depths"].iloc[0])[:-1]
        all_x, interp_lons, interp_lats = get_polyline_profile(current_line, df_up_map, resolution_m=50)
        
        # 5. Get Stations and Boreholes
        stations_on_line = get_station_projections(current_line, df_up_map, search_radius_m=self.settings.radius)
        
        # Safe check for bh_data (assuming it's a class attribute or global)
        bh_data = getattr(self, 'bh_data', None) 
        bh_projections = []
        if bh_data is not None:
            bh_projections = get_borehole_projections(current_line, bh_data, view, search_radius_m=self.settings.radius)

        # 6. Check for Data Availability
        if not stations_on_line and not bh_projections:
            return self.empty_figure(f"No data found within {self.settings.radius}m of the line.")

        # 7. Calculate Path Elevations
        if stations_on_line:
            st_x = [s['dist_x'] for s in stations_on_line]
            st_z = [s['elev'] for s in stations_on_line]
            path_elevations = np.interp(all_x, st_x, st_z) if len(st_x) > 1 else np.full_like(all_x, st_z[0])
        elif bh_projections:
            avg_elev = np.mean([b['elev'] for b in bh_projections])
            path_elevations = np.full_like(all_x, avg_elev)
        else:
            path_elevations = np.zeros_like(all_x)

        # 8. Build Figure based on Mode
        if mode == "blocky":
            fig = create_blocky_polygons(stations_on_line, y_depth, bar_width=30) if stations_on_line else go.Figure()
        elif mode == "interp":
            samples = np.vstack([interp_lons, interp_lats]).T
            res_models, _, _, _ = interpolate_nearest(df_up_map, samples, radius=self.settings.radius)
            fig = plot_section_topographic(all_x, y_depth, res_models, elev=path_elevations)
        elif mode == "combined":
            samples = np.vstack([interp_lons, interp_lats]).T
            res_models, _, _, _ = interpolate_nearest(df_up_map, samples, radius=self.settings.radius)
            fig = combine_sections_final(all_x, y_depth, res_models, path_elevations, stations_on_line)
        else:
            fig = go.Figure()

        # 9. Add Boreholes if they exist
        if bh_projections:
            # Assuming rock_color_map is available globally or via self
            rock_map = getattr(self, 'rock_color_map', None)
            fig = add_boreholes_to_fig(fig, bh_projections, rock_map)

        # 10. Final Layout Adjustments
        all_x_vals = list(all_x)
        if stations_on_line:
            all_x_vals.extend([s['dist_x'] for s in stations_on_line])
        
        x_min, x_max = min(all_x_vals), max(all_x_vals)
        padding = (x_max - x_min) * 0.1 if x_max != x_min else 50
        
        fig.update_layout(
            xaxis=dict(range=[x_min - padding, x_max + padding], title="Distance (m)"),
            yaxis=dict(title="Elevation (m)"),
            hovermode='closest',
            template="plotly_white")
        print("FIG DATA TRACES:", len(fig.data))
        return fig

    def render(self, **kwargs):
       
        # Extract parameters from the callback trigger
        lines = kwargs.get('lines')
        mode = kwargs.get('mode', 'blocky')
        selected_idx = kwargs.get('selected_idx')
        view = kwargs.get('view')
        if lines is None: return self.empty_render()
        # 1. Generate the Figure object
        fig = self.get_figure(lines, mode, selected_idx, view)

        # 2. Determine if we show a colorbar
        has_data = lines is not None and len(lines) > 0
        
        # 3. Build the UI Components
        # graph_element = dcc.Graph(
        #     id='profile_plot_main',
        #     figure=fig,
        #     style={"height": "100%", "width": "100%"},
        #     config={"displayModeBar": True, "responsive": True})

        legend_element = None
        if has_data and mode in ["blocky", "interp", "combined"]:
            legend_bar = create_geologic_colorbar_horizontal(
                self.settings.res_min, 
                self.settings.res_max, 
                bar_height=18)
            legend_element = html.Div(legend_bar, style={"width": "80%", "margin": "10px auto"})

        # 4. Construct Final Layout
        # children_list = [html.Div(graph_element, style={"flex": "1", "minHeight": 0, "width": "100%"})]

        # if legend_element:
        #     children_list.append(legend_element)

        # content = html.Div(children=children_list, style={"display": "flex","flexDirection": "column","height": "100%","width": "100%"})

        # 5. Return content
        return fig

    
    def initialize(self):            
        return html.Div([
            # --- STORES ---
            # html.Div(id="window-container", style={"position": "relative", "zIndex": 9999}), # --- for ctrl + alt + left click and show models  ---
            dcc.Store(id="combined-window-store", data={"window_id": None, "indices": []}),            
            dcc.Store(id="right-click-index-store", data=None),
            dcc.Store(id='active-windows-store', data=[]),  

            dcc.Store(id="line-preview-store"),
            dcc.Store(id="line-final-store"),
            dcc.Store(id="section-mode-store", data="blocky"),
            dcc.Store(id="map-view-store"),
            dcc.Store(id="selected-line-index", data=0),
            dcc.Store(id="map-hover-marker-store", data=None),
            dcc.Store(id="map-settings-store", data={}),
            dcc.Store(id='global-color-map-store', data=color_master_map if self.dataframe is not None else None),
            dcc.Store(id="points-available-attrs-store", data=existing_attrs if self.dataframe is not None else 'date'),
            dcc.Store(id="profile-busy-store", data=False),
            dcc.Store(id="profile-load-trigger", data=0),
            super().initialize()
            ])
    #         html.Div(
    #                 id="profile-plot-container",
    #                 style={
    #                     "flex": "1", "position": "relative", "minHeight": 0,
    #                     "background": "white", "borderRadius": "8px",
    #                     "boxShadow": "0 0 10px rgba(0,0,0,0.15)", "padding": "5px",
    #                     "display": "flex", "flexDirection": "column", "overflow": "hidden",
    #                 },
    #                 children=[
    #                     # 1. THE OVERLAY (Now outside the content div)
    #                     # html.Div(
    #                     #     id="profile-busy-overlay",
    #                     #     children= "Preparing profile...",                                            
    #                     #     style={
    #                     #         "display": "none", # Hidden by default
    #                     #         "position": "absolute", "top": "120px", "left": "12px", "right": "auto",
    #                     #         "padding": "6px 15px", "background": "rgba(0,0,0,0.8)",
    #                     #         "color": "white", "zIndex": 9999, "borderRadius": "6px"
    #                     #     }
    #                     # ),
    #                     # 2. THE CONTENT AREA (This is what the callback targets)
    #                     # html.Div(
    #                     #     id="profile-plot-content_2",
    #                     #     style= {"flex": "1","width": "100%", "height": "100%",
    #                     #             # "justifyContent": "center","alignItems": "center"
    #                     #             "display": "flex",
    #                     #             "flexDirection": "column",
    #                     #             "minHeight": 0,
    #                     #             },
    #                     #     children=[
    #                     dcc.Graph(
    #                         id="profile_plot_main", 
    #                         figure=self.render(),
    #                     style={ "height": "100%", "width": "100%", "background": "white", "borderRadius": "8px", "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)" 
    #                             }
    #                         )
    #                     ],
    #                     ),
    #                 # ],
    #             # ),                       
    #         gear_maker(self.id)
    #     ])
        