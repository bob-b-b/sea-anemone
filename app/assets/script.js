// Open dialogue window before leaving the page
window.addEventListener('beforeunload', function (e) {
    e.preventDefault();
    e.returnValue = true;
});

// Shutdown the server if the usere exits
window.addEventListener("unload", function (e) {
    fetch('/shutdown', { method: 'POST' });
});