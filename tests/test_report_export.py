from types import SimpleNamespace

import numpy as np
import pandas as pd

from app.report_export import (
    build_interpretation_docx,
    filter_models_for_export,
    update_export_exclusions,
)


def test_export_site_exclusions_are_reversible_and_do_not_mutate_models():
    models = pd.DataFrame({"site_id": [1, 1, 2, -1], "resistivity": [10, 20, 30, 40]})

    excluded = update_export_exclusions([], [np.int64(1)], exclude=True)
    included = update_export_exclusions(excluded, [1], exclude=False)
    filtered = filter_models_for_export(models, excluded)

    assert excluded == [1]
    assert type(excluded[0]) is int
    assert included == []
    assert filtered["site_id"].tolist() == [2]
    assert models["site_id"].tolist() == [1, 1, 2, -1]


def test_word_report_contains_only_non_excluded_model_rows():
    models = pd.DataFrame(
        {
            "site_id": [1, 2],
            "layer": [1, 1],
            "resistivity": [10.0, 100.0],
            "top_depth": [0.0, 0.0],
            "bottom_depth": [10.0, 20.0],
            "doi": [10.0, 20.0],
            "misfit": [1.0, 2.0],
            "elevation": [50.0, 60.0],
        }
    )
    sites = pd.DataFrame(
        {
            "site_id": [1, 2],
            "latitude": [56.0, 56.1],
            "longitude": [10.0, 10.1],
        }
    )
    session = SimpleNamespace(
        data=pd.DataFrame({"site_id": [1, 2]}),
        models=models,
        site=sites,
        save_dir=None,
    )

    report = build_interpretation_docx(
        session,
        excluded_sites=[1],
        map_settings=SimpleNamespace(plot_by="site_id"),
        model_settings=SimpleNamespace(
            x_axis="site_id",
            y_axis="depth",
            doi=True,
            misfit=True,
            bars=True,
            vmin=1.0,
            vmax=500.0,
        ),
    )

    from docx import Document
    from io import BytesIO

    document = Document(BytesIO(report))
    document_text = "\n".join(
        cell.text
        for table in document.tables
        for row in table.rows
        for cell in row.cells
    )
    assert "2" in document_text
    assert "100.0" in document_text
    assert "10.0" not in document_text
    assert len(document.inline_shapes) == 2
