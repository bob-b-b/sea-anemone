// Track Alt and Ctrl key state for click modifiers
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