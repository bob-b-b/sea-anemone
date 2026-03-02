"""
Borehole utilities for Sea Anemone.

Handles parsing .bor files, coordinate projection, and visualization
on both map and section plots.
"""

import re
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from pyproj import Transformer


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def load_borehole_file(file_path_or_content, from_string=False):
    """
    Parse a .bor file and return (all_boreholes, rock_color_map).

    Parameters
    ----------
    file_path_or_content : str
        Path to a .bor file, or the raw text content if *from_string* is True.
    from_string : bool
        If True, treat the first argument as file content rather than a path.

    Returns
    -------
    all_boreholes : list[dict]
        Each dict has keys: bh_index, id, x, y, elevation, utm_zone, datum, layers
    rock_color_map : dict
        Mapping from LayerDescription -> hex colour string.
    """
    if from_string:
        content = file_path_or_content
    else:
        with open(file_path_or_content, "r") as f:
            content = f.read()

    blocks = re.split(r"(?=BoreholeNo=)", content)
    blocks = [b.strip() for b in blocks if "BoreholeNo=" in b]

    all_boreholes = []

    for i, block in enumerate(blocks):
        def _get(field, text=block):
            m = re.search(f"{field}=(.*)", text)
            return m.group(1).strip() if m else None

        try:
            bh_id = _get("BoreholeNo")
            elev  = float(_get("Elevation"))
            utm_zone_raw = _get("UTMZone")
            datum_raw    = _get("Datum")

            # Auto-detect EPSG from UTMZone + Datum
            utm_zone = int(utm_zone_raw) if utm_zone_raw else 37
            datum    = (datum_raw or "WGS84").upper()
            if "WGS" in datum or "84" in datum:
                epsg = 32600 + utm_zone          # WGS-84 northern hemisphere
            else:
                epsg = 32600 + utm_zone          # fallback to WGS-84

            bh_metadata = {
                "bh_index": i,
                "id": bh_id,
                "x": float(_get("XUTM")),
                "y": float(_get("YUTM")),
                "elevation": elev,
                "utm_zone": utm_zone,
                "epsg": epsg,
            }

            table_start = block.find("Top")
            if table_start == -1:
                continue

            table_lines = block[table_start:].strip().split("\n")
            if len(table_lines) < 2:
                continue

            data_rows = []
            for line in table_lines[1:]:
                parts = re.findall(r'(".*?"|\S+)', line)
                if len(parts) >= 2:
                    while len(parts) < 4:
                        parts.append("")
                    data_rows.append({
                        "Top": float(parts[0]),
                        "Bottom": float(parts[1]),
                        "LayerDescription": parts[2].replace('"', ''),
                        "RockType": parts[3],
                    })

            df_layers = pd.DataFrame(data_rows)
            if not df_layers.empty:
                df_layers["RockType"] = df_layers["RockType"].replace(
                    {"Nan": "Unspecified", "": "Unspecified"}
                )
                bh_metadata["layers"] = df_layers.to_dict("records")
                all_boreholes.append(bh_metadata)

        except Exception as e:
            print(f"Error parsing borehole {i}: {e}")

    # --- Global colour map ---
    all_rock_types = set()
    for bh in all_boreholes:
        for layer in bh["layers"]:
            rt = layer["LayerDescription"]
            if rt:
                all_rock_types.add(rt)

    sorted_rocks = sorted(all_rock_types)
    cmap = plt.get_cmap("tab20b")
    rock_color_map = {}
    if sorted_rocks:
        positions = np.linspace(0.1, 0.9, len(sorted_rocks))
        for idx, rock in enumerate(sorted_rocks):
            rock_color_map[rock] = mcolors.to_hex(cmap(positions[idx]))

    return all_boreholes, rock_color_map


# ---------------------------------------------------------------------------
# Coordinate projection  (UTM -> WGS-84 lat/lon)
# ---------------------------------------------------------------------------

def get_borehole_projections(boreholes, src_epsg=None):
    """
    Convert borehole UTM coordinates to WGS-84 lat/lon for map display.

    Parameters
    ----------
    boreholes : list[dict]
        Output of load_borehole_file().
    src_epsg : int or None
        Source EPSG code.  If None, each borehole's own ``epsg`` key is used.

    Returns
    -------
    list[dict]
        Each entry has: id, map_lon, map_lat, elev, layers.
    """
    if isinstance(boreholes, dict):
        boreholes = [boreholes]

    projections = []
    _cache = {}                       # transformer cache keyed by epsg

    for bh in boreholes:
        epsg = src_epsg or bh.get("epsg", 32637)
        if epsg not in _cache:
            _cache[epsg] = Transformer.from_crs(
                f"EPSG:{epsg}", "EPSG:4326", always_xy=True
            )
        transformer = _cache[epsg]
        lon, lat = transformer.transform(bh["x"], bh["y"])

        projections.append({
            "id": bh["id"],
            "map_lon": lon,
            "map_lat": lat,
            "elev": bh["elevation"],
            "layers": bh["layers"],
        })

    return projections


# ---------------------------------------------------------------------------
# Map overlay
# ---------------------------------------------------------------------------

def add_boreholes_to_map_fig(fig, bh_projections, bh_color="orange"):
    """
    Add borehole markers to a Plotly Scattermap figure.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure
    bh_projections : list[dict]
        Output of get_borehole_projections().
    bh_color : str
        Marker colour.
    """
    if not bh_projections:
        return fig

    lons  = [b["map_lon"] for b in bh_projections]
    lats  = [b["map_lat"] for b in bh_projections]
    names = [b["id"]      for b in bh_projections]

    # customdata carries [bh_id, 0, "borehole"] so Alt+click can identify type
    cdata = [[b["id"], 0, "borehole"] for b in bh_projections]

    fig.add_trace(go.Scattermap(
        lat=lats,
        lon=lons,
        mode="markers+text",
        marker=dict(size=14, color=bh_color, symbol="circle"),
        text=names,
        textposition="top right",
        customdata=cdata,
        name="Boreholes",
        showlegend=False,
        below="",
    ))
    return fig


# ---------------------------------------------------------------------------
# Section overlay  (borehole columns on a resistivity section)
# ---------------------------------------------------------------------------

def add_boreholes_to_section_fig(
    fig,
    bh_projections,
    rock_color_map,
    section_df=None,
    x_axis="site_id",
    column_width=6,
):
    """
    Overlay borehole lithology columns onto a model-section figure.

    For x_axis in ('longitude', 'latitude', 'distance') the borehole is
    placed at its matching coordinate.  For x_axis == 'site_id' the closest
    site_id position is used.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure
    bh_projections : list[dict]
    rock_color_map : dict
    section_df : pd.DataFrame or None
        The model section dataframe.  Used to locate the borehole along the
        section's x-axis.
    x_axis : str
    column_width : float
    """
    if not bh_projections:
        return fig

    for bh in bh_projections:
        # --- Determine x-position along the section axis ---
        bh_x = _find_bh_x_position(bh, section_df, x_axis)
        if bh_x is None:
            continue

        for layer in bh["layers"]:
            z_top    = bh["elev"] - float(layer["Top"])
            z_bottom = bh["elev"] - float(layer["Bottom"])
            hw = column_width / 2.0

            x_box = [bh_x - hw, bh_x + hw, bh_x + hw, bh_x - hw, bh_x - hw]
            y_box = [z_top, z_top, z_bottom, z_bottom, z_top]

            rock  = layer.get("LayerDescription", "").strip()
            color = rock_color_map.get(rock, "lightgray")

            fig.add_trace(go.Scatter(
                x=x_box, y=y_box,
                fill="toself",
                fillcolor=color,
                mode="lines",
                line=dict(width=0.5, color="black"),
                name=rock,
                showlegend=False,
                hovertext=f"{bh['id']}: {rock}",
                hoverinfo="text",
            ))

        # Label at top
        fig.add_annotation(
            x=bh_x,
            y=bh["elev"],
            text=f"<b>{bh['id']}</b>",
            showarrow=False,
            yshift=10,
            xanchor="center",
            yanchor="bottom",
            font=dict(size=10, color="black"),
        )

    return fig


def _find_bh_x_position(bh, section_df, x_axis):
    """Return the x-coordinate for a borehole on the section axis, or None."""
    if x_axis in ("longitude",):
        return bh.get("map_lon")
    if x_axis in ("latitude",):
        return bh.get("map_lat")

    if section_df is not None and not section_df.empty:
        # Find the closest site by Euclidean distance on lat/lon
        if "longitude" in section_df.columns and "latitude" in section_df.columns:
            lon, lat = bh["map_lon"], bh["map_lat"]
            dists = np.sqrt(
                (section_df["longitude"] - lon) ** 2
                + (section_df["latitude"] - lat) ** 2
            )
            closest_idx = dists.idxmin()
            return section_df.loc[closest_idx, x_axis]

    return None


# ---------------------------------------------------------------------------
# Standalone borehole comparison figure
# ---------------------------------------------------------------------------

def build_combined_borehole_figure(bh_ids, bh_projections, rock_color_map):
    """
    Create a side-by-side borehole lithology figure.

    Parameters
    ----------
    bh_ids : list[str]
    bh_projections : list[dict]
    rock_color_map : dict

    Returns
    -------
    plotly.graph_objects.Figure
    """
    fig = go.Figure()
    valid_indices = []

    for x_pos, target_id in enumerate(bh_ids):
        bh = next(
            (b for b in bh_projections
             if str(b.get("id")) == str(target_id)),
            None,
        )
        if not bh:
            continue
        valid_indices.append(x_pos)

        for layer in bh.get("layers", []):
            z_top    = bh["elev"] - float(layer["Top"])
            z_bottom = bh["elev"] - float(layer["Bottom"])
            w = 0.4
            x_box = [x_pos - w, x_pos + w, x_pos + w, x_pos - w, x_pos - w]
            y_box = [z_top, z_top, z_bottom, z_bottom, z_top]

            rock  = layer.get("LayerDescription", "").strip()
            color = rock_color_map.get(rock, "lightgray")

            fig.add_trace(go.Scatter(
                x=x_box, y=y_box,
                fill="toself",
                fillcolor=color,
                mode="lines",
                line=dict(width=0.8, color="black"),
                name=rock,
                showlegend=False,
                hovertext=(
                    f"<b>{bh['id']}</b><br>{rock}<br>"
                    f"Elev: {z_top:.1f} to {z_bottom:.1f}m"
                ),
                hoverinfo="text",
            ))

        fig.add_annotation(
            x=x_pos, y=bh["elev"],
            text=f"<b>{bh['id']}</b>",
            showarrow=False, yshift=15,
            font=dict(size=12),
        )

    x_min = (min(valid_indices) - 1) if valid_indices else -1
    x_max = (max(valid_indices) + 1) if valid_indices else  1

    fig.update_layout(
        template="plotly_white",
        showlegend=False,
        xaxis=dict(
            tickvals=list(range(len(bh_ids))),
            ticktext=bh_ids,
            title="Borehole ID",
            range=[x_min, x_max],
            showgrid=False,
            linecolor="black", mirror=True,
        ),
        yaxis=dict(
            title="Elevation (m.a.s.l.)",
            gridcolor="lightgray",
            linecolor="black", mirror=True,
        ),
        margin=dict(l=60, r=40, t=50, b=60),
    )
    return fig


# ---------------------------------------------------------------------------
# Line projection utilities  (draw line → filter boreholes by radius)
# ---------------------------------------------------------------------------

def haversine_distance(p1, p2):
    """Distance in metres between two [lon, lat] points."""
    lon1, lat1 = np.radians(p1)
    lon2, lat2 = np.radians(p2)
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * np.arcsin(np.sqrt(a))


def project_point_onto_polyline(station_pt, polyline_coords):
    """
    Project a [lon, lat] point onto a polyline.

    Returns (distance_along_line_m, perpendicular_distance_m).
    """
    best_x = 0
    min_dist = float("inf")
    cum_dist = 0
    for i in range(len(polyline_coords) - 1):
        A = np.array(polyline_coords[i])
        B = np.array(polyline_coords[i + 1])
        P = np.array(station_pt)
        seg_len = haversine_distance(A, B)
        if seg_len == 0:
            continue
        ab = B - A
        t = np.clip(np.dot(P - A, ab) / np.dot(ab, ab), 0, 1)
        closest = A + t * ab
        d = haversine_distance(P, closest)
        if d < min_dist:
            min_dist = d
            best_x = cum_dist + t * seg_len
        cum_dist += seg_len
    return best_x, min_dist


def get_boreholes_on_line(line_coords, bh_projections, search_radius_m=50):
    """
    Filter bh_projections to those within *search_radius_m* of *line_coords*
    and add a ``dist_x`` key (distance along the line in metres).

    Parameters
    ----------
    line_coords : list of [lon, lat]
    bh_projections : list[dict]   (output of get_borehole_projections)
    search_radius_m : float

    Returns
    -------
    list[dict]  — filtered and enriched with ``dist_x``.
    """
    if not line_coords or len(line_coords) < 2:
        return []
    result = []
    for bh in bh_projections:
        pt = [bh["map_lon"], bh["map_lat"]]
        dist_along, dist_from = project_point_onto_polyline(pt, line_coords)
        if dist_from <= search_radius_m:
            entry = dict(bh)          # shallow copy
            entry["dist_x"] = dist_along
            result.append(entry)
    return sorted(result, key=lambda x: x["dist_x"])
