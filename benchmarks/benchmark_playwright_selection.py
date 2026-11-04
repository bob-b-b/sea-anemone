import importlib.util
import statistics
import sys
import threading
from pathlib import Path

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Page, expect
from werkzeug.serving import make_server


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ARCHIVE = ROOT / "Data" / "L003_S033_2025_1113_125719.zip"
LINKED_GRAPHS = ("sounding", "rhoa", "tTEM")
sys.path.append(str(ROOT / "app"))
import temframe
from session import Session


@pytest.fixture(scope="module")
def selection_app_url():
    with SAMPLE_ARCHIVE.open("rb") as archive:
        data, forwards = temframe.from_zip_content(archive.read())
    sample_session = Session(data=data, forwards=forwards)
    sample_session.update_site_table()
    main_module = sys.modules["__main__"]
    had_previous_session = hasattr(main_module, "sesh")
    previous_session = getattr(main_module, "sesh", None)
    main_module.sesh = sample_session

    app_path = ROOT / "app" / "app.py"
    spec = importlib.util.spec_from_file_location(
        "sea_anemone_benchmark_app", app_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load application module from {app_path}")
    dash_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = dash_module
    spec.loader.exec_module(dash_module)
    dash_module.sesh = sample_session
    dash_module.m1.dataframe = sample_session.overview
    dash_module.dbdt1.dataframe = sample_session.data.copy()
    dash_module.dbdt2.dataframe = sample_session.data.copy()
    dash_module.rhoa.dataframe = sample_session.data.copy()
    dash_module.flex_layout.model = dash_module.layouts.data
    dash_module.flex_layout.children = [
        node for panel in dash_module.panels for node in panel.to_nodes()
    ]
    server = make_server("127.0.0.1", 0, dash_module.app.server, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        if had_previous_session:
            main_module.sesh = previous_session
        else:
            del main_module.sesh


def _site_ids_from_plot(graph):
    return graph.evaluate(
        """gd => [...new Set(gd.data
            .flatMap(trace => trace.customdata?._inputArray ?? trace.customdata ?? [])
            .filter(row => row.length > 2 && row[2] != null)
            .map(row => String(row[2])))]"""
    )


def test_map_selection_updates_linked_plots(
    page: Page, benchmark, selection_app_url: str, capsys
):
    response = page.goto(selection_app_url, wait_until="domcontentloaded")
    assert response is not None and response.status == 200
    expect(page).to_have_title("Sea Anemone")

    page.locator("#process_layout").click()

    for graph_id in ("map", *LINKED_GRAPHS):
        page.locator(f"#{graph_id} .js-plotly-plot").wait_for(
            state="visible", timeout=60_000
        )

    map_graph = page.locator("#map .js-plotly-plot")
    site_trace = map_graph.evaluate(
        """gd => gd.data.findIndex(trace => trace.name === "sites")"""
    )
    assert site_trace >= 0, "Map site trace missing"
    site_count = map_graph.evaluate(
        """(gd, traceIndex) => {
            const customdata = gd.data[traceIndex].customdata;
            return (customdata?._inputArray ?? customdata ?? []).length;
        }""",
        site_trace,
    )
    assert site_count >= 2, f"Expected multiple map sites, got {site_count}"

    site_ids = map_graph.evaluate(
        """(gd, traceIndex) => {
            const customdata = gd.data[traceIndex].customdata;
            const rows = customdata?._inputArray ?? customdata ?? [];
            return [String(rows[0][0]), String(rows.at(-1)[0])];
        }""",
        site_trace,
    )
    linked_graphs = [
        page.locator(f"#{graph_id} .js-plotly-plot") for graph_id in LINKED_GRAPHS
    ]
    section_graph = linked_graphs[-1]
    measured_latencies = []
    selection_index = 0

    def select_site_and_wait():
        nonlocal selection_index
        site_id = site_ids[selection_index % len(site_ids)]
        selection_index += 1
        expected_x = float(site_id)
        current_site_trace = map_graph.evaluate(
            """gd => gd.data.findIndex(trace => trace.name === "sites")"""
        )
        assert current_site_trace >= 0, "Map site trace missing after selection"

        page.evaluate(
            """({siteId, traceIndex}) => {
                window.__selectionBenchmarkStart = performance.now();
                window.__selectionBenchmarkEnd = null;
                window.dash_clientside.set_props("map", {
                    selectedData: {
                        points: [{curveNumber: traceIndex, customdata: [Number(siteId)]}]
                    }
                });
            }""",
            arg={"siteId": site_id, "traceIndex": current_site_trace},
        )

        for graph_id, graph in zip(LINKED_GRAPHS, linked_graphs):
            try:
                page.wait_for_function(
                    """({graphId, siteId}) => {
                        const graph = document.querySelector(`#${graphId} .js-plotly-plot`);
                        if (!graph) return false;
                        const hasSite = graph.data.some(trace =>
                            (trace.customdata?._inputArray ?? trace.customdata ?? [])
                                .some(row => String(row[2]) === siteId)
                        );
                        if (!hasSite) return false;
                        if (graphId === "tTEM") {
                            const range = graph.layout.xaxis?.range;
                            const x = Number(siteId);
                            const zoomed = range?.length === 2 &&
                                Math.abs(Number(range[0]) - x) < 1e-6 &&
                                Math.abs(Number(range[1]) - x) < 1e-6;
                            if (!zoomed) return false;
                            if (window.__selectionBenchmarkEnd === null) {
                                requestAnimationFrame(() => requestAnimationFrame(() => {
                                    window.__selectionBenchmarkEnd = performance.now();
                                }));
                            }
                            return window.__selectionBenchmarkEnd !== null;
                        }
                        const ready = graph.data
                            .flatMap(trace => trace.customdata?._inputArray ?? trace.customdata ?? [])
                            .every(row => String(row[2]) === siteId);
                        return ready;
                    }""",
                    arg={"graphId": graph_id, "siteId": site_id},
                    polling="raf",
                    timeout=8_000,
                )
            except PlaywrightTimeoutError as exc:
                state = graph.evaluate(
                    """gd => ({
                        sites: [...new Set(gd.data
                            .flatMap(trace => trace.customdata?._inputArray ?? trace.customdata ?? [])
                            .map(row => String(row[2])))]
                            .slice(0, 10),
                        range: gd.layout.xaxis?.range,
                    })"""
                )
                raise AssertionError(
                    f"{graph_id} did not visibly update for site {site_id}: {state}"
                ) from exc

        elapsed_ms = page.evaluate(
            "window.__selectionBenchmarkEnd - window.__selectionBenchmarkStart"
        )
        assert _site_ids_from_plot(linked_graphs[0]) == [site_id]
        assert _site_ids_from_plot(linked_graphs[1]) == [site_id]
        assert site_id in _site_ids_from_plot(section_graph)
        section_range = section_graph.evaluate("gd => gd.layout.xaxis.range")
        assert section_range == [expected_x, expected_x]
        measured_latencies.append(elapsed_ms)

    benchmark.pedantic(
        select_site_and_wait,
        rounds=10,
        iterations=1,
        warmup_rounds=0,
    )
    benchmark.extra_info["browser-visible update median (ms)"] = round(
        statistics.median(measured_latencies), 2
    )
    benchmark.extra_info["browser-visible update max (ms)"] = round(
        max(measured_latencies), 2
    )
    with capsys.disabled():
        print(
            "Browser-visible update latency: "
            f"median={statistics.median(measured_latencies):.2f} ms, "
            f"max={max(measured_latencies):.2f} ms"
        )
