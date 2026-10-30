// Click-to-draw survey lines on the map (map panel "Draw line" button, or the L key).
// While drawing: each click on the map adds a node, a double-click finishes the line (drawing stays on for the next
// one), Backspace removes the last node, Escape drops the line in progress. Turning drawing off keeps the line in
// progress if it has at least two nodes.
// Clicks are converted to lon/lat by the maplibre map underneath plotly, so no server round trip is needed until a
// line is finished: the line in progress is drawn by restyling the map's 'draft' trace, and start/stop/finished lines
// go to the server through the 'map_line_draw' store (handled in Map.add_callbacks, map.py).
// Listeners sit on the document in the capture phase, so they survive the map being re-mounted when the layout
// changes and the clicks never reach plotly (no site highlight on click, no view reset on double-click).
(function () {
    if (window.anemoneLineDraw !== undefined) return;
    const state = window.anemoneLineDraw = { active: false, nodes: [], cursor: null, down: null, frame: null };

    function mapGd() { return document.querySelector('#map .js-plotly-plot'); }

    function maplibre(gd) {
        const subplot = gd && gd._fullLayout && gd._fullLayout.map && gd._fullLayout.map._subplot;
        return subplot ? subplot.map : null;
    }

    // [lon, lat] under the mouse, or null if the event is not on the map itself
    function eventLonLat(e) {
        const map = maplibre(mapGd());
        if (!map || !e.target.closest || !e.target.closest('#map') || e.target.closest('.modebar')) return null;
        const r = map.getCanvas().getBoundingClientRect();
        const x = e.clientX - r.left, y = e.clientY - r.top;
        if (x < 0 || y < 0 || x > r.width || y > r.height) return null;
        const p = map.unproject([x, y]);
        return [p.lng, p.lat];
    }

    function redraw() {
        state.frame = null;
        const gd = mapGd();
        if (!gd || !gd.data) return;
        const i = gd.data.findIndex(t => t.name === 'draft');
        if (i < 0) return;
        const pts = state.nodes.concat(state.active && state.cursor && state.nodes.length ? [state.cursor] : []);
        Plotly.restyle(gd, { lon: [pts.map(p => p[0])], lat: [pts.map(p => p[1])] }, [i]);
    }

    function scheduleRedraw() {
        if (state.frame === null) state.frame = requestAnimationFrame(redraw);
    }

    function takeLine(action) {
        const nodes = state.nodes.length >= 2 ? state.nodes : [];
        state.nodes = [];
        scheduleRedraw();
        return { action: action, nodes: nodes, ts: Date.now() };
    }

    document.addEventListener('mousedown', e => { state.down = [e.clientX, e.clientY]; }, true);

    document.addEventListener('click', e => {
        if (!state.active) return;
        const ll = eventLonLat(e);
        if (!ll) return;
        e.stopPropagation();
        // a click that ends a pan is not a node
        if (state.down && Math.hypot(e.clientX - state.down[0], e.clientY - state.down[1]) > 4) return;
        state.nodes.push(ll);
        scheduleRedraw();
    }, true);

    document.addEventListener('dblclick', e => {
        if (!state.active || !eventLonLat(e)) return;
        e.stopPropagation();
        e.preventDefault();
        // both clicks of the double-click added a node at the same spot
        const n = state.nodes.length;
        if (n >= 2 && Math.abs(state.nodes[n-1][0] - state.nodes[n-2][0]) + Math.abs(state.nodes[n-1][1] - state.nodes[n-2][1]) < 1e-6) {
            state.nodes.pop();
        }
        if (state.nodes.length >= 2) window.dash_clientside.set_props('map_line_draw', { data: takeLine('line') });
    }, true);

    document.addEventListener('mousemove', e => {
        if (!state.active) return;
        state.cursor = eventLonLat(e);
        const map = maplibre(mapGd());
        if (map) map.getCanvas().style.cursor = 'crosshair';
        if (state.nodes.length) scheduleRedraw();
    }, true);

    document.addEventListener('keydown', e => {
        if (!state.active) return;
        const el = document.activeElement;
        if (el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.isContentEditable)) return;
        if (e.key === 'Escape') {
            state.nodes = [];
            scheduleRedraw();
        } else if (e.key === 'Backspace' && state.nodes.length) {
            state.nodes.pop();
            scheduleRedraw();
            e.preventDefault();
        }
    });

    window.dash_clientside = Object.assign({}, window.dash_clientside);
    window.dash_clientside.anemone = Object.assign({}, window.dash_clientside.anemone, {
        // map_drawline button -> map_line_draw store
        toggleLineDraw: function (n_clicks) {
            if (!state.active) {
                state.active = true;
                state.nodes = [];
                return { action: 'start', nodes: [], ts: Date.now() };
            }
            state.active = false;
            const map = maplibre(mapGd());
            if (map) map.getCanvas().style.cursor = '';
            return takeLine('stop');
        }
    });
})();
