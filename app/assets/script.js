// Open dialogue window before leaving the page
window.addEventListener('beforeunload', function (e) {
    e.preventDefault();
    e.returnValue = true;
});

// Shutdown the server if the usere exits
window.addEventListener("unload", function (e) {
    fetch('/shutdown', { method: 'POST' });
});


if (window._keyTracker === undefined) {
    window._keyTracker = { alt: false, ctrl: false };
    window.addEventListener('keydown', (e) => { 
        if (e.key === 'Alt') window._keyTracker.alt = true; 
        if (e.key === 'Control') window._keyTracker.ctrl = true;
    });
    window.addEventListener('keyup', (e) => { 
        if (e.key === 'Alt') window._keyTracker.alt = false; 
        if (e.key === 'Control') window._keyTracker.ctrl = false;
    });
}


// Open dialogue window before leaving the page
window.addEventListener('beforeunload', function (e) {
    e.preventDefault();
    e.returnValue = true;
});

// Shutdown the server if the usere exits
window.addEventListener("unload", function (e) {
    fetch('/shutdown', { method: 'POST' });
});


(function () {
  if (window._windowManagerInit) return;
  window._windowManagerInit = true;

  let z = 1000;

  function bringToFront(win) {
    z += 1;
    win.style.zIndex = z;
  }

  document.addEventListener("mousedown", function (e) {
    // Start drag if clicking a header
    const header = e.target.closest(".window-header");
    const win = e.target.closest(".draggable-window");

    // If clicked anywhere inside a window, bring it to front
    if (win) bringToFront(win);

    if (!header) return;
    if (!win) return;

    // Don't drag if clicking the close button
    if (e.target.closest("button")) return;

    e.preventDefault();

    const rect = win.getBoundingClientRect();
    const shiftX = e.clientX - rect.left;
    const shiftY = e.clientY - rect.top;

    function move(ev) {
      win.style.left = (ev.clientX - shiftX) + "px";
      win.style.top = (ev.clientY - shiftY) + "px";
    }

    function stop() {
      document.removeEventListener("mousemove", move);
      document.removeEventListener("mouseup", stop);
    }

    document.addEventListener("mousemove", move);
    document.addEventListener("mouseup", stop);
  });

  console.log("✅ window_manager.js loaded (drag + z-index)");
})();
