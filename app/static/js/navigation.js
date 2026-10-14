/**
 * Interceptor SPA-like para transiciones suaves de página (v1.1.0)
 * Extrae únicamente `#main-content` y actualiza el DOM sin recargas bruscas.
 */

(function() {
    'use strict';

    const progressBar = document.getElementById('pageProgressBar');
    let progressTimer = null;

    function startProgress() {
        if (!progressBar) return;
        clearInterval(progressTimer);
        progressBar.classList.add('loading');
        progressBar.style.width = '25%';
        progressBar.style.opacity = '1';

        progressTimer = setInterval(() => {
            const currentWidth = parseFloat(progressBar.style.width) || 25;
            if (currentWidth < 85) {
                progressBar.style.width = (currentWidth + Math.random() * 15) + '%';
            }
        }, 120);
    }

    function completeProgress() {
        if (!progressBar) return;
        clearInterval(progressTimer);
        progressBar.style.width = '100%';
        setTimeout(() => {
            progressBar.style.opacity = '0';
            setTimeout(() => {
                progressBar.style.width = '0%';
                progressBar.classList.remove('loading');
            }, 300);
        }, 150);
    }

    function isEligibleLink(anchor) {
        if (!anchor || anchor.tagName !== 'A') return false;
        const href = anchor.getAttribute('href');
        if (!href) return false;

        // Ignorar anclas vacías o hashes
        if (href.startsWith('#') || href.startsWith('javascript:')) return false;

        // Ignorar enlaces externos o protocolos especiales
        if (anchor.target === '_blank' || anchor.getAttribute('download') !== null) return false;
        if (href.startsWith('mailto:') || href.startsWith('tel:') || href.startsWith('https://wa.me')) return false;

        // Ignorar exclusiones explícitas
        if (anchor.hasAttribute('data-no-pjax')) return false;

        // Ignorar rutas administrativas y autenticación crítica
        if (href.includes('/admin') || href.includes('/auth/logout') || href.includes('/set-language')) return false;

        // Comprobar mismo origen
        try {
            const url = new URL(anchor.href, window.location.origin);
            return url.origin === window.location.origin;
        } catch(e) {
            return false;
        }
    }

    async function loadPage(url, push = true) {
        const mainContent = document.getElementById('main-content');
        if (!mainContent) {
            window.location.href = url;
            return;
        }

        startProgress();

        // Transición de salida suave (150ms)
        mainContent.style.transition = 'opacity 150ms ease, transform 150ms ease';
        mainContent.style.opacity = '0';
        mainContent.style.transform = 'translateY(6px)';

        try {
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            if (!response.ok) {
                window.location.href = url;
                return;
            }

            const html = await response.text();
            const parser = new DOMParser();
            const newDoc = parser.parseFromString(html, 'text/html');
            const newMain = newDoc.getElementById('main-content');

            if (!newMain) {
                // Si la nueva página no tiene #main-content (ej. error inesperado), fallback nativo
                window.location.href = url;
                return;
            }

            // Actualizar título
            if (newDoc.title) {
                document.title = newDoc.title;
            }

            // Actualizar contenido principal
            mainContent.innerHTML = newMain.innerHTML;
            mainContent.className = newMain.className;

            // Actualizar badge del carrito si cambió
            const newCartBadge = newDoc.querySelector('.cart-badge');
            const currentCartBadge = document.querySelector('.cart-badge');
            if (newCartBadge && currentCartBadge) {
                currentCartBadge.textContent = newCartBadge.textContent;
            }

            // Gestionar historial de navegación
            if (push) {
                history.pushState({ url: url }, '', url);
            }

            // Desplazar suavemente arriba
            window.scrollTo({ top: 0, behavior: 'instant' });

            // Transición de entrada suave
            requestAnimationFrame(() => {
                mainContent.style.opacity = '1';
                mainContent.style.transform = 'translateY(0)';
            });

            // Reinicializar componentes de página
            if (typeof window.initPageEnhancements === 'function') {
                window.initPageEnhancements();
            }
            if (typeof window.initCartAsync === 'function') {
                window.initCartAsync();
            }

            completeProgress();
        } catch (err) {
            completeProgress();
            // Fallback a navegación estándar ante cualquier excepción
            window.location.href = url;
        }
    }

    // Interceptar clics en enlaces globales
    document.addEventListener('click', (e) => {
        // Ignorar clics con modificadores (Ctrl, Shift, Meta, Alt)
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.defaultPrevented) return;

        const anchor = e.target.closest('a');
        if (isEligibleLink(anchor)) {
            e.preventDefault();
            loadPage(anchor.href, true);
        }
    });

    // Soporte para los botones Atrás / Adelante del navegador
    window.addEventListener('popstate', (e) => {
        if (e.state && e.state.url) {
            loadPage(e.state.url, false);
        } else {
            loadPage(window.location.href, false);
        }
    });
})();
