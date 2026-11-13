/** Navegación nativa: conserva CSP, scripts, formularios e historial de cada documento. */
(function () {
    'use strict';
    const bar = document.getElementById('pageProgressBar');
    document.addEventListener('click', event => {
        if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
        const anchor = event.target.closest('a');
        if (!anchor || anchor.target || anchor.hasAttribute('download')) return;
        const url = new URL(anchor.href, location.href);
        if (url.origin !== location.origin || (url.pathname === location.pathname && url.search === location.search && url.hash)) return;
        if (bar) { bar.style.width = '70%'; bar.style.opacity = '1'; }
    });
    window.addEventListener('pageshow', () => {
        if (bar) { bar.style.width = '0'; bar.style.opacity = '0'; }
    });
})();
