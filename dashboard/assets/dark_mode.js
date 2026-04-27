// Dark mode toggle — watches theme-store localStorage for changes
(function() {
    function applyTheme() {
        var raw = localStorage.getItem('theme-store');
        var theme = 'light';
        if (raw) {
            try { theme = JSON.parse(raw); } catch(e) { theme = raw; }
        }
        if (typeof theme === 'string') {
            theme = theme.replace(/"/g, '');
        }
        document.documentElement.setAttribute('data-theme', theme === 'dark' ? 'dark' : 'light');
    }

    // Apply on load
    applyTheme();

    // Watch for localStorage changes (from Dash dcc.Store)
    window.addEventListener('storage', applyTheme);

    // Also poll every 500ms (dcc.Store updates don't always fire storage event)
    setInterval(applyTheme, 500);
})();
