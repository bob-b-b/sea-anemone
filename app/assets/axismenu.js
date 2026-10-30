// Click an axis title (or the map's colour bar title) to pick what it shows from a small menu.
// A figure opts in through layout.meta.menus = {x: menu, y: menu, colorbar: menu} (built by basepanel.axis_menu), where
// menu = {target, options, value, live}: picking an option sets `value` on the dash component `target` (the panel's existing
// dropdown or settings field), so the panel's own callbacks do the re-render. Options and value are read live from the
// target component when it has them (e.g. line options added after drawing on the map; live: false turns this off for
// options), else from the menu itself.
// A figure can also make an annotation open a menu by naming it 'menu:<key>' (used by the map when it has no colour bar).
(function () {
    if (window.anemoneAxisMenu !== undefined) return;
    const state = window.anemoneAxisMenu = { popup: null };

    // which menu (if any) a click on `el` opens: [graph div, menu key]
    function menuAt(el) {
        if (!el || !el.closest) return null;
        const gd = el.closest('.js-plotly-plot');
        const menus = gd && gd.layout && gd.layout.meta && gd.layout.meta.menus;
        if (!menus) return null;
        let key = null;
        for (let node = el; node && node !== gd && !key; node = node.parentNode) {
            const cls = node.classList;
            if (!cls) continue;
            if ([...cls].some(c => /^g-x\d*title$/.test(c))) key = 'x';
            else if ([...cls].some(c => /^g-y\d*title$/.test(c))) key = 'y';
            else if (cls.contains('cbtitle')) key = 'colorbar';
            else if (cls.contains('annotation')) {
                const ann = (gd.layout.annotations || [])[+node.getAttribute('data-index')];
                if (ann && typeof ann.name === 'string' && ann.name.startsWith('menu:')) key = ann.name.slice(5);
            }
        }
        return key && menus[key] ? [gd, key] : null;
    }

    function liveProps(target) {
        try {
            const c = window.dash_component_api && window.dash_component_api.getLayout(target);
            return (c && c.props) || {};
        } catch (e) { return {}; }
    }

    function close() {
        if (state.popup) state.popup.remove();
        state.popup = null;
    }

    function open(menu, x, y) {
        close();
        const live = liveProps(menu.target);
        const options = ((menu.live !== false && live.options) || menu.options || []).map(o => typeof o === 'object' ? o : { label: String(o), value: o });
        const value = live.value !== undefined ? live.value : menu.value;
        const popup = state.popup = document.createElement('div');
        popup.className = 'dropdown-menu show axis-menu';
        options.forEach(o => {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'dropdown-item' + (String(o.value) === String(value) ? ' active' : '');
            item.textContent = o.label === '' ? '(none)' : o.label;
            item.addEventListener('click', () => {
                close();
                if (String(o.value) !== String(value)) window.dash_clientside.set_props(menu.target, { value: o.value });
            });
            popup.appendChild(item);
        });
        document.body.appendChild(popup);
        // keep the menu inside the window
        const r = popup.getBoundingClientRect();
        popup.style.left = Math.max(4, Math.min(x, window.innerWidth - r.width - 4)) + 'px';
        popup.style.top = Math.max(4, Math.min(y, window.innerHeight - r.height - 4)) + 'px';
    }

    document.addEventListener('click', function (e) {
        if (state.popup && state.popup.contains(e.target)) return;
        const hit = menuAt(e.target);
        close();
        if (!hit) return;
        const [gd, key] = hit;
        e.stopPropagation();
        open(gd.layout.meta.menus[key], e.clientX, e.clientY);
    }, true);

    // pointer + underline only on titles that actually open a menu
    document.addEventListener('mouseover', function (e) {
        const t = e.target;
        if (t && t.tagName === 'text' && menuAt(t)) t.classList.add('axis-menu-title');
    }, true);

    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); }, true);
    window.addEventListener('blur', close);
})();
