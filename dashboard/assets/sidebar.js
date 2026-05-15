/* Sidebar: toggle collapse + localStorage + active link */
(function () {
  var KEY = 'emh-sidebar';

  function getSidebar() { return document.getElementById('sidebar'); }

  function applyState(collapsed) {
    var sb = getSidebar();
    if (!sb) return;
    sb.classList.toggle('collapsed', collapsed);
  }

  function setActiveLinks() {
    var path = window.location.pathname;
    document.querySelectorAll('.sb-item[href]').forEach(function (a) {
      var href = a.getAttribute('href');
      var active = href === path || (href === '/' && path === '/');
      a.classList.toggle('active', active);
    });
  }

  // Apply saved state on first load
  document.addEventListener('DOMContentLoaded', function () {
    var saved = localStorage.getItem(KEY);
    applyState(saved === 'collapsed');
    setActiveLinks();

    // Toggle button
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('#sb-toggle-btn');
      if (!btn) return;
      var sb = getSidebar();
      if (!sb) return;
      var collapsed = sb.classList.toggle('collapsed');
      localStorage.setItem(KEY, collapsed ? 'collapsed' : 'expanded');
    });
  });

  // Dash re-renders page content on navigation — re-run active link detection
  var observer = new MutationObserver(setActiveLinks);
  document.addEventListener('DOMContentLoaded', function () {
    var content = document.getElementById('page-content');
    if (content) {
      observer.observe(content, { childList: true });
    }
    // Also watch for URL changes via Dash's dcc.Location
    window.addEventListener('popstate', setActiveLinks);
  });
})();
