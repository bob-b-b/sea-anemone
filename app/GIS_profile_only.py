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

import matplotlib.pyplot as plt
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.plot import reshape_as_image

from dash import Dash, html, dcc, Input, Output, State, no_update, callback_context
from dash.dependencies import Input, Output, State, ALL, MATCH

from pydantic import Field

from Map_external_layers import GIS_helpers
from Sections_plotting import *


@nosj
class ProfileSettings(PanelSettings):
    vmin: int = 1
    vmax: int = 300
    log: bool = True
    cmap: str = 'turbo'
    nticks: int = 4
    Show_misfit : bool =True

    radius: int = 50 
    num_labels_colorbar: int = 4

    column_width: int = 6 

    @classmethod
    def _create_schema(cls):
        class tmp(cls, JsonSchemaMixin):
            pass
        schema = tmp.json_schema()
        
        if 'properties' in schema and 'column_width' in schema['properties']:
            schema['properties']['column_width'].update({
                "type": "integer",  # Explicitly tell the UI it's an int
                "title": "Bar Width (1-9)",
                "minimum": 1,
                "maximum": 9,
                "step": 1
            })
        return schema


class Profile(Panel):
    def __init__(self, dataframe, **kwargs):
                    
        settings = kwargs.pop('settings', ProfileSettings(id='profile_plot_main'))       
        super().__init__(id = 'profile_plot_main', settings=settings)
        self.dataframe = dataframe

        for key, value in kwargs.items():
            setattr(self, key, value)

    def empty_figure(self, msg="No profile selected."):
        fig = go.Figure()
        fig.add_annotation(text=msg, showarrow=False, font=dict(size=16, color="gray"))
        # fig.update_layout(xaxis=dict(visible=False), yaxis=dict(visible=False), margin=dict(t=0,b=0,l=0,r=0))
        return fig
    
    def get_direction_label(self, lons, lats):
        if len(lons) < 2:
            return "Profile"
        
        # Calculate change in coordinates
        d_lon = lons[-1] - lons[0]
        d_lat = lats[-1] - lats[0]
        
        # Calculate angle in degrees (0 is East, 90 is North, etc.)
        angle = np.degrees(np.arctan2(d_lat, d_lon))
        
        # Map angle to 8 cardinal/intercardinal points
        # Normalize to 0-360
        angle = (angle + 360) % 360
        
        if 22.5 <= angle < 67.5:    return "SW - NE"
        elif 67.5 <= angle < 112.5:  return "S - N"
        elif 112.5 <= angle < 157.5: return "SE - NW"
        elif 157.5 <= angle < 202.5: return "E - W"
        elif 202.5 <= angle < 247.5: return "NE - SW"
        elif 247.5 <= angle < 292.5: return "N - S"
        elif 292.5 <= angle < 337.5: return "NW - SE"
        else: return "W - E"


    def get_figure(self, lines, mode, selected_idx, view, title='Profile'):
        if lines is None or (isinstance(lines, pd.DataFrame) and lines.empty):
            return self.empty_render()

        # 2. Extract Data Context (Updated for DataFrame)
        try:
            # Get unique line IDs (e.g., [1.0, 2.0])
            unique_lines = lines['line'].unique()
            
            # Determine which line ID to use
            idx = selected_idx if selected_idx is not None else 0
            if idx >= len(unique_lines):
                idx = -1 # Default to last line
                
            line_id = unique_lines[idx]
            current_line_df = lines[lines['line'] == line_id].sort_index()
            current_line = current_line_df[['longitude', 'latitude']].values.tolist()
            
        except (IndexError, TypeError, KeyError) as e:
            print(f"Error extracting line: {e}")
            return self.empty_figure("Error selecting line data.")


        # 3. Pre-process Dataframe
        # Note: self.dataframe is passed during __init__
        df_up_map, color_master_map, existing_attrs = preprocess_new_df(self.dataframe)
        
        # 4. Gather Geometry Data
        y_depth = np.array(df_up_map["Depths"].iloc[0])[:-1]
        all_x, interp_lons, interp_lats = get_polyline_profile(current_line, df_up_map, resolution_m=50)
        direction = self.get_direction_label(interp_lons, interp_lats)
        dynamic_title = f"Profile {int(line_id)}: {direction}"

        # 5. Get Stations and Boreholes
        stations_on_line = get_station_projections(current_line, df_up_map, search_radius_m=self.settings.radius)
        
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
            fig = create_blocky_polygons(stations_on_line, y_depth, self.settings.vmin, self.settings.vmax, self.settings.log, self.settings.Show_misfit, bar_width=self.settings.column_width) if stations_on_line else go.Figure() 
        elif mode == "interp":
            samples = np.vstack([interp_lons, interp_lats]).T
            res_models, _, _, _ , dois= interpolate_nearest(df_up_map, samples, radius=self.settings.radius)
            fig = plot_section_topographic(all_x, y_depth, self.settings.vmin, self.settings.vmax, self.settings.log, res_models, elev=path_elevations, dois=dois)
        elif mode == "combined":
            samples = np.vstack([interp_lons, interp_lats]).T
            res_models, _, _, _, dois = interpolate_nearest(df_up_map, samples, radius=self.settings.radius)
            fig = combine_sections_final(all_x, y_depth, self.settings.vmin, self.settings.vmax, self.settings.log, res_models, path_elevations, stations_on_line,dois=dois, show_misfit=self.settings.Show_misfit,  bar_width=self.settings.column_width)
        else:
            fig = go.Figure()

        # 9. Add Boreholes if they exist
        if bh_projections:
            rock_map = rock_color_map
            fig = add_boreholes_to_fig(fig, bh_projections, rock_map)

        # 10. Final Layout Adjustments
        all_x_vals = list(all_x)
        if stations_on_line:
            all_x_vals.extend([s['dist_x'] for s in stations_on_line])
        
        x_min, x_max = min(all_x_vals), max(all_x_vals)
        padding = (x_max - x_min) * 0.1 if x_max != x_min else 50
       
        fig.update_layout(
            title=dict(text=dynamic_title, x=0.5, xanchor='center'), 
            xaxis=dict(range=[x_min - padding, x_max + padding], title="Distance (m)"),
            yaxis=dict(title="Elevation (m)"),
            hovermode='closest',
            template="plotly_white",
        )
        return fig

    def render(self, **kwargs):
        lines = kwargs.get('lines')
        mode = kwargs.get('mode', 'blocky')
        selected_idx = kwargs.get('selected_idx')
        view = kwargs.get('view')
        width_int = getattr(self.settings, 'column_width', 6)
        vmin = self.settings.vmin
        vmax = self.settings.vmax

        log_vmin = np.log10(vmin)
        log_vmax = np.log10(vmax)
        
        is_empty = lines is None or (isinstance(lines, pd.DataFrame) and lines.empty)
        
        if is_empty:
            fig = self.empty_figure("Draw a line to generate a profile.")
        else:
            # If lines came as a list of dicts (from a Store), convert to DF
            if isinstance(lines, (list, dict)):
                lines = pd.DataFrame(lines)
                
            # 3. Call your core figure generation logic
            fig = self.get_figure(lines, mode, selected_idx, view)            
            
            # 4. Colorbar Setup
            tick_vals = np.linspace(log_vmin, log_vmax, self.settings.nticks)
            tick_text = [f"{10**v:.0f}" for v in tick_vals]
            
            fig.add_trace(go.Scatter(
                        x=[None], y=[None],
                        mode='markers',
                        marker=dict(
                            colorscale=getattr(self.settings, 'cmap', 'viridis'),
                            showscale=True,
                            cmin=log_vmin,
                            cmax=log_vmax,
                            color=[log_vmin, log_vmax],
                            colorbar=dict(
                                # title="Resistivity (Ωm)",
                                orientation='h',x=0.5, xanchor='center',y=-0.2,yanchor='top',thickness=20,len=0.95,
                                tickmode='array',  tickvals=list(tick_vals), ticktext=tick_text,)),
                        hoverinfo='none',showlegend=False))

                    # 2. Adjust Layout for the extra space below
            fig.update_layout(margin=dict(b=80), # Increase bottom margin to make room for colorbar
                coloraxis_showscale=False,
                coloraxis_colorbar_exponentformat="power",)
        return fig
    
    def initialize(self):            
        return html.Div(style={"height": "100%","display": "flex","flexDirection": "column","minHeight": 0},
            children=[ # --- STORES ---
            html.Div(id="window-container", style={"position": "relative", "zIndex": 9999}), # --- for ctrl + alt + left click and show models  ---
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
            dcc.Store(id='global-color-map-store', data=None),#color_master_map if self.dataframe is not None else None),
            dcc.Store(id="points-available-attrs-store", data=None),# if self.dataframe is not None else 'date'),
            dcc.Store(id="profile-busy-store", data=False),
            dcc.Store(id="profile-load-trigger", data=0),
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
                             # --- Section Mode Button ---
                            html.Div(
                                style={"position": "relative"},
                                children=[
                                    html.Button("Section ▼", id="section-toggle", style={"padding": "5px 10px"}),
                                    html.Div(
                                        id="section-panel",
                                        style={"display": "none", "position": "absolute", "background": "white", "padding": "8px", "borderRadius": "6px", "boxShadow": "0 2px 6px rgba(0,0,0,0.25)", "marginTop": "4px", "minWidth": "140px"},
                                        children=[
                                            html.Div("Interpolated", id={"type": "section-option", "mode": "interp"}, style={"padding": "6px", "cursor": "pointer"}),
                                            html.Div("Column Bar(s)", id={"type": "section-option", "mode": "blocky"}, style={"padding": "6px", "cursor": "pointer"}),
                                            html.Div("Combined", id={"type": "section-option", "mode": "combined"}, style={"padding": "6px", "cursor": "pointer"}),
                                        ],
                                    ),
                                ]
                            ),                                                    
                        ],
                    ),
            html.Div(
                    id="profile-plot-container",
                    style={
                        "flex": "1", "position": "relative", "minHeight": 0,
                        "background": "white", "borderRadius": "8px",
                        "boxShadow": "0 0 10px rgba(0,0,0,0.15)", "padding": "5px",
                        "display": "flex", "flexDirection": "column", "overflow": "hidden",
                    },
                    children=[
                        # 1. THE OVERLAY (Now outside the content div)
                        html.Div(
                            id="profile-busy-overlay",
                            children= "Preparing profile...",                                            
                            style={
                                "display": "none", # Hidden by default
                                "position": "absolute", "top": "120px", "left": "12px", "right": "auto",
                                "padding": "6px 15px", "background": "rgba(0,0,0,0.8)",
                                "color": "white", "zIndex": 9999, "borderRadius": "6px"
                            }
                        ),
                        # 2. THE CONTENT AREA (This is what the callback targets)
                        html.Div(
                            id="profile-plot-content_2",
                            style= {"flex": "1","width": "100%", "height": "100%",
                                    "display": "flex",
                                    "flexDirection": "column",
                                    "minHeight": 0,
                                    "position": "relative",
                                    },
                            children=[
                        dcc.Graph(
                            id="profile_plot_main", 
                            figure=self.empty_figure("Draw a line to generate a profile."),
                        style={ "height": "100%", "width": "100%", "background": "white", "borderRadius": "8px", "boxShadow": "0 -2px 10px rgba(0,0,0,0.1)" 
                                }
                            ),
                    html.Div(
                        style={
                                "padding": "10px 15px", # Space around the text
                                "background": "#f9f9f9", # Light background to distinguish it
                                "borderTop": "1px solid #eee", # Clean separation line
                                "fontSize": "14px",
                                "color": "#666",
                                "display": "flex",
                                "gap": "15px" # Puts horizontal space between the two shortcuts
                            },
                                children=[
                                    html.Div([
                                            html.Span("Profile Plot\nKeyboard Shortcuts: ", style={"fontWeight": "bold"}),
                                            ]),
                                    html.Div([
                                            html.Span("Alt + Left Click: ", style={"fontWeight": "bold"}),
                                            html.Span("Single TEM or Borehole Window"),]),
                                    html.Div([
                                            html.Span("Ctrl + Alt + Left Click: ", style={"fontWeight": "bold"}),
                                            html.Span("Multiple TEM or Borehole Window"),
                                            ], ), 
                        ],
                        ),
                    
                    ]),
                    ],
                ),                       
            gear_maker(self.id)
        ])
        # ])
        