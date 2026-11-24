import importlib
import sys
from types import ModuleType, SimpleNamespace


def test_dash_root_and_layout_routes(monkeypatch):
    tkinter = ModuleType("tkinter")
    tkinter.Tk = object
    tkinter.filedialog = ModuleType("tkinter.filedialog")
    monkeypatch.setitem(sys.modules, "tkinter", tkinter)
    monkeypatch.setitem(sys.modules, "tkinter.filedialog", tkinter.filedialog)

    monkeypatch.setattr(
        sys.modules["__main__"],
        "sesh",
        SimpleNamespace(
            data=None,
            models=None,
            lines=None,
            overview=None,
            save_dir=None,
            forwards=None,
        ),
        raising=False,
    )

    dash_app = importlib.import_module("app.app")
    client = dash_app.app.server.test_client()

    ui_callback_entry = next(
        callback
        for callback in dash_app.app.callback_map.values()
        if "callback" in callback
        and getattr(callback["callback"], "__wrapped__", None)
        and callback["callback"].__wrapped__.__name__ == "interpret_mode_ui"
    )
    ui_callback = ui_callback_entry["callback"].__wrapped__
    callback_outputs = ui_callback_entry["output"]
    assert len(ui_callback("secondary")) == len(callback_outputs)
    assert len(ui_callback("primary")) == len(callback_outputs)

    page = client.get("/")
    layout = client.get("/_dash-layout")

    assert page.status_code == 200
    assert b"Sea Anemone" in page.data
    assert layout.status_code == 200
    assert b"flex-layout" in layout.data
    assert b"table-overview-source" in layout.data
    assert b"Input measurements" in layout.data
    assert b"Inversion results" in layout.data
    assert b"data-loading-overlay" in layout.data
    assert b"inversion-loading-overlay" in layout.data
    assert b"inv-timer" in layout.data