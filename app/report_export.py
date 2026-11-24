from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pandas as pd


def _plain_scalar(value):
    return value.item() if isinstance(value, np.generic) else value


def update_export_exclusions(current_sites, selected_sites, exclude):
    sites = {_plain_scalar(site) for site in current_sites or ()}
    selected = {_plain_scalar(site) for site in selected_sites or ()}
    if exclude:
        sites.update(selected)
    else:
        sites.difference_update(selected)
    return sorted(sites, key=str)


def filter_models_for_export(models, excluded_sites):
    if models is None:
        return pd.DataFrame()
    if "site_id" not in models.columns:
        raise ValueError("Model data must include a site_id column.")
    excluded_sites = set(excluded_sites or ())
    return models.loc[
        (models["site_id"] != -1) & ~models["site_id"].isin(excluded_sites)
    ].copy()


def _site_table(session, models, excluded_sites):
    sites = session.site
    if sites is None and session.data is not None:
        columns = [
            column
            for column in ("site_id", "latitude", "longitude", "elevation", "date")
            if column in session.data.columns
        ]
        sites = session.data[columns].drop_duplicates("site_id")
    if sites is None:
        return pd.DataFrame()

    sites = sites.loc[
        (sites["site_id"] != -1) & ~sites["site_id"].isin(excluded_sites)
    ].copy()
    if not models.empty:
        model_counts = models.groupby("site_id").size().rename("model_layers")
        sites = sites.merge(model_counts, how="left", on="site_id")
        sites["model_layers"] = sites["model_layers"].fillna(0).astype(int)
    return sites


def _map_png(sites, color_by):
    if sites.empty or not {"latitude", "longitude"}.issubset(sites.columns):
        return None

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(8, 4.5), constrained_layout=True)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    color_values = None
    if color_by in sites.columns and pd.api.types.is_numeric_dtype(sites[color_by]):
        color_values = sites[color_by]
    points = axis.scatter(
        sites["longitude"],
        sites["latitude"],
        c=color_values,
        cmap="turbo" if color_values is not None else None,
        edgecolors="black",
        linewidths=0.4,
    )
    if color_values is not None:
        figure.colorbar(points, ax=axis, label=color_by)
    axis.set(title="Included sites", xlabel="Longitude", ylabel="Latitude")
    axis.grid(True, alpha=0.25)
    image = BytesIO()
    figure.savefig(image, format="png", dpi=150)
    return image.getvalue()


def _model_section_png(models, settings):
    required = {"site_id", "resistivity", "top_depth", "bottom_depth"}
    if models.empty or not required.issubset(models.columns):
        return None

    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.colors import LogNorm
    from matplotlib.figure import Figure
    from matplotlib.patches import Rectangle
    from matplotlib.collections import PatchCollection
    from matplotlib.cm import ScalarMappable

    valid = models.loc[
        (models["site_id"] != -1)
        & models["resistivity"].gt(0)
        & models["top_depth"].notna()
        & models["bottom_depth"].notna()
    ].copy()
    if valid.empty:
        return None

    x_axis = getattr(settings, "x_axis", "site_id")
    if x_axis not in valid.columns:
        x_axis = "site_id"
    x_by_site = valid.groupby("site_id", sort=False)[x_axis].first()
    if pd.api.types.is_datetime64_any_dtype(x_by_site):
        from matplotlib.dates import date2num

        x_values = date2num(pd.to_datetime(x_by_site).dt.to_pydatetime())
    else:
        x_values = pd.to_numeric(x_by_site, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(x_values).all() or len(np.unique(x_values)) != len(x_values):
        x_axis = "site_id"
        x_by_site = x_by_site.iloc[np.argsort(x_by_site.index)]
        x_values = np.arange(len(x_by_site), dtype=float)
    else:
        order = np.argsort(x_values)
        x_by_site = x_by_site.iloc[order]
        x_values = np.asarray(x_values)[order]

    sites = x_by_site.index.tolist()
    if len(x_values) == 1:
        site_widths = np.array([0.8])
    else:
        spacing = np.diff(x_values)
        site_widths = np.empty(len(x_values))
        site_widths[0], site_widths[-1] = spacing[0], spacing[-1]
        if len(x_values) > 2:
            site_widths[1:-1] = np.minimum(spacing[:-1], spacing[1:])
        site_widths *= 0.8
    site_x = dict(zip(sites, x_values))
    site_width = dict(zip(sites, site_widths))
    y_axis = getattr(settings, "y_axis", "depth")
    if y_axis == "elevation" and (
        "elevation" not in valid.columns or valid["elevation"].isna().any()
    ):
        y_axis = "depth"
    patches = []
    values = []
    for row in valid.itertuples(index=False):
        top = float(row.top_depth)
        bottom = float(row.bottom_depth)
        if y_axis == "elevation" and hasattr(row, "elevation") and pd.notna(row.elevation):
            top, bottom = float(row.elevation) - top, float(row.elevation) - bottom
        lower, upper = sorted((top, bottom))
        if upper <= lower:
            continue
        patches.append(
            Rectangle(
                (site_x[row.site_id] - site_width[row.site_id] / 2, lower),
                site_width[row.site_id],
                upper - lower,
            )
        )
        values.append(float(row.resistivity))
    if not patches:
        return None

    minimum = max(float(getattr(settings, "vmin", min(values))), min(values))
    maximum = max(float(getattr(settings, "vmax", max(values))), max(values))
    if maximum <= minimum:
        maximum = minimum * 1.001
    norm = LogNorm(vmin=minimum, vmax=maximum)
    figure = Figure(figsize=(10, 5), constrained_layout=True)
    FigureCanvasAgg(figure)
    axis = figure.subplots()
    collection = PatchCollection(
        patches,
        cmap="turbo",
        norm=norm,
        edgecolor="white",
        linewidth=0.25,
    )
    collection.set_array(np.asarray(values))
    axis.add_collection(collection)
    axis.set_xlim(
        min(x_values - site_widths / 2),
        max(x_values + site_widths / 2),
    )
    axis.set_ylim(min(p.get_y() for p in patches), max(p.get_y() + p.get_height() for p in patches))
    if y_axis != "elevation":
        axis.invert_yaxis()

    tick_count = min(len(sites), 12)
    tick_positions = np.unique(np.linspace(0, len(sites) - 1, tick_count, dtype=int))
    axis.set_xticks(x_values[tick_positions])
    axis.set_xticklabels([str(sites[index]) for index in tick_positions])
    x_label = (
        "Distance along line [m]"
        if x_axis.startswith("_line")
        else x_axis.replace("_", " ").title()
    )
    axis.set(
        title="Resistivity model section",
        xlabel=x_label,
        ylabel="Elevation [m]" if y_axis == "elevation" else "Depth [m]",
    )
    axis.grid(True, alpha=0.2)
    figure.colorbar(
        ScalarMappable(norm=norm, cmap="turbo"),
        ax=axis,
        label="Resistivity [Ω·m]",
    )
    image = BytesIO()
    figure.savefig(image, format="png", dpi=150)
    return image.getvalue()


def build_interpretation_docx(session, excluded_sites, map_settings, model_settings):
    from docx import Document
    from docx.shared import Inches

    excluded_sites = set(excluded_sites or ())
    models = filter_models_for_export(session.models, excluded_sites)
    sites = _site_table(session, models, excluded_sites)
    document = Document()
    document.add_heading("Sea Anemone interpretation report", level=0)
    document.add_paragraph(f"Generated {datetime.now().astimezone():%Y-%m-%d %H:%M %Z}")

    document.add_heading("Project summary", level=1)
    project_name = (
        Path(session.save_dir.rstrip("\\/")).name
        if session.save_dir
        else "Sea Anemone project"
    )
    total_sites = (
        int(session.data.loc[session.data["site_id"] != -1, "site_id"].nunique())
        if session.data is not None and "site_id" in session.data.columns
        else len(sites) + len(excluded_sites)
    )
    summary = document.add_table(rows=0, cols=2)
    summary.style = "Light Shading Accent 1"
    for label, value in (
        ("Project", project_name),
        ("Sites in source data", total_sites),
        ("Sites included in this report", len(sites)),
        ("Sites excluded from this report", len(excluded_sites)),
        (
            "Excluded site IDs",
            ", ".join(str(site) for site in sorted(excluded_sites, key=str))
            or "None",
        ),
        ("Model layers included", len(models)),
    ):
        cells = summary.add_row().cells
        cells[0].text = str(label)
        cells[1].text = str(value)

    document.add_heading("Interpretation plots", level=1)
    map_image = _map_png(sites, getattr(map_settings, "plot_by", ""))
    if map_image is None:
        document.add_paragraph("Site coordinates are not available for a map.")
    else:
        document.add_picture(BytesIO(map_image), width=Inches(6.5))

    model_image = _model_section_png(models, model_settings)
    if model_image is None:
        document.add_paragraph("No model layers are available to plot.")
    else:
        document.add_picture(BytesIO(model_image), width=Inches(6.5))

    document.add_heading("Interpretation settings", level=1)
    settings_table = document.add_table(rows=0, cols=2)
    settings_table.style = "Light Shading Accent 1"
    settings = (
        ("Map colour by", getattr(map_settings, "plot_by", "not set")),
        ("Section x-axis", getattr(model_settings, "x_axis", "not set")),
        ("Section y-axis", getattr(model_settings, "y_axis", "not set")),
        ("Show DOI", getattr(model_settings, "doi", "not set")),
        ("Show misfit", getattr(model_settings, "misfit", "not set")),
        ("Show bars", getattr(model_settings, "bars", "not set")),
        ("Resistivity range [Ω·m]", f"{getattr(model_settings, 'vmin', 'not set')}–{getattr(model_settings, 'vmax', 'not set')}"),
    )
    for label, value in settings:
        cells = settings_table.add_row().cells
        cells[0].text = str(label)
        cells[1].text = str(value)

    document.add_heading("Included model data", level=1)
    columns = [
        column
        for column in (
            "site_id",
            "layer",
            "resistivity",
            "top_depth",
            "bottom_depth",
            "doi",
            "misfit",
        )
        if column in models.columns
    ]
    if models.empty or not columns:
        document.add_paragraph("No model data are available for the selected sites.")
    else:
        data_table = document.add_table(rows=1, cols=len(columns))
        data_table.style = "Light Shading Accent 1"
        for cell, column in zip(data_table.rows[0].cells, columns):
            cell.text = column.replace("_", " ").title()
        for row in models[columns].itertuples(index=False, name=None):
            cells = data_table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = "" if pd.isna(value) else str(value)

    output = BytesIO()
    document.save(output)
    return output.getvalue()


def report_filename(session):
    project = (
        Path(session.save_dir.rstrip("\\/")).name
        if session.save_dir
        else "SeaAnemone"
    )
    safe_project = "".join(
        character if character.isalnum() or character in "-_" else "_"
        for character in project
    ).strip("_") or "SeaAnemone"
    return f"{safe_project}_interpretation.docx"
