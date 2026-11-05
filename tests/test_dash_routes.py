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

    page = client.get("/")
    layout = client.get("/_dash-layout")

    assert page.status_code == 200
    assert b"Sea Anemone" in page.data
    assert layout.status_code == 200
    assert b"flex-layout" in layout.data