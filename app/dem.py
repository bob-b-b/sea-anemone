
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