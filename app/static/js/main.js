// Scripts principales de la ferretería web (v1.1.0)
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// Inicializador general de la aplicación
function initApp() {
    initFlashAlerts();
    initThemeToggle();
    initBackToTop();
    initMobileMenu();
    initScrollReveal();
    initWideDetails();
}

// Paneles <details data-open-wide>: abiertos en escritorio, plegables en móvil
function initWideDetails() {
    const wide = window.matchMedia('(min-width: 861px)');
    const sync = () => document.querySelectorAll('details[data-open-wide]').forEach(d => {
        if (wide.matches) d.open = true;
    });
    sync();
    if (!document.documentElement.dataset.wideBound) {
        document.documentElement.dataset.wideBound = 'true';
        wide.addEventListener('change', sync);
    }
}

// Cierre suave de alertas de Flask
function initFlashAlerts() {
    // Los errores permanecen visibles hasta que el usuario los cierre.
    document.querySelectorAll('.flash-container .alert, .admin-main .alert').forEach(alert => {
        if (alert.querySelector('.alert-close')) return;
        const close = document.createElement('button');
        close.type = 'button'; close.className = 'toast-close alert-close';
        close.setAttribute('aria-label', 'Cerrar mensaje');
        close.innerHTML = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
        close.addEventListener('click', () => alert.remove());
        alert.append(close);
    });
}

// Alternar tema Claro / Oscuro con persistencia en localStorage
function initThemeToggle() {
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        try {
            localStorage.setItem('theme', newTheme);
        } catch(e) {}
    }

    const publicToggle = document.getElementById('themeToggle');
    const adminToggle = document.getElementById('themeToggleAdmin');

    if (publicToggle && !publicToggle.dataset.bound) {
        publicToggle.dataset.bound = "true";
        publicToggle.addEventListener('click', toggleTheme);
    }
    if (adminToggle && !adminToggle.dataset.bound) {
        adminToggle.dataset.bound = "true";
        adminToggle.addEventListener('click', toggleTheme);
    }
}

// Botón Volver Arriba (Back to Top)
function initBackToTop() {
    const backToTopBtn = document.getElementById('backToTopBtn');
    if (!backToTopBtn) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 300) {
            backToTopBtn.classList.add('show');
        } else {
            backToTopBtn.classList.remove('show');
        }
    }, { passive: true });

    if (!backToTopBtn.dataset.bound) {
        backToTopBtn.dataset.bound = "true";
        backToTopBtn.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'
            });
        });
    }
}

// Menú Móvil (Hamburger & Drawer)
function initMobileMenu() {
    const menuBtn = document.getElementById('mobileMenuBtn');
    const navLinks = document.getElementById('navLinks');
    const overlay = document.getElementById('mobileOverlay');

    if (!menuBtn || !navLinks) return;

    function toggleMenu() {
        const isOpen = navLinks.classList.toggle('mobile-open');
        menuBtn.classList.toggle('open', isOpen);
        menuBtn.setAttribute('aria-expanded', isOpen);
        if (overlay) overlay.classList.toggle('active', isOpen);
    }

    function closeMenu() {
        navLinks.classList.remove('mobile-open');
        menuBtn.classList.remove('open');
        menuBtn.setAttribute('aria-expanded', 'false');
        if (overlay) overlay.classList.remove('active');
    }

    if (!menuBtn.dataset.bound) {
        menuBtn.dataset.bound = "true";
        menuBtn.addEventListener('click', toggleMenu);
    }

    if (overlay && !overlay.dataset.bound) {
        overlay.dataset.bound = "true";
        overlay.addEventListener('click', closeMenu);
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') closeMenu();
    });
}

// Animaciones suaves al hacer scroll (Scroll Reveal)
function initScrollReveal() {
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const revealElements = document.querySelectorAll(
        '.reveal-on-scroll, .product-card, .category-card, .kpi-card, .feature-item, .contact-card'
    );

    const observer = new IntersectionObserver((entries, obs) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('reveal-visible');
                obs.unobserve(entry.target);
            }
        });
    }, {
        threshold: 0.1,
        rootMargin: '0px 0px -40px 0px'
    });

    revealElements.forEach(el => {
        el.classList.add('reveal-on-scroll');
        observer.observe(el);
    });
}

// Sistema de Notificaciones Toast Flotantes (v1.2.0)
function showToast(message, type = 'info', duration = 2800) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    // Evitar apilar más de 2 notificaciones simultáneas
    while (container.children.length >= 2) {
        container.removeChild(container.firstElementChild);
    }

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;

    // Iconos SVG de trazo uniforme (sin emojis). Contenido estático y de confianza.
    const svg = (d) => '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + d + '</svg>';
    const icons = {
        success: svg('<path d="m5 12.5 4.5 4.5L19 7.5"/>'),
        danger: svg('<path d="M18 6 6 18M6 6l12 12"/>'),
        error: svg('<path d="M18 6 6 18M6 6l12 12"/>'),
        warning: svg('<path d="M12 8v5M12 17h.01"/>'),
        info: svg('<path d="M12 11v5M12 8h.01"/>')
    };

    toast.setAttribute('role', type === 'danger' || type === 'error' ? 'alert' : 'status');

    // Banda de señal de obra: una palabra que se lee de un vistazo
    const en = document.documentElement.lang === 'en';
    const words = en
        ? { success: 'Done', danger: 'Error', error: 'Error', warning: 'Caution', info: 'Notice' }
        : { success: 'Listo', danger: 'Error', error: 'Error', warning: 'Precaución', info: 'Aviso' };
    const bandEl = document.createElement('span');
    bandEl.className = 'toast-band';
    const iconEl = document.createElement('span');
    iconEl.className = 'toast-icon';
    iconEl.innerHTML = icons[type] || icons.info;
    const wordEl = document.createElement('span');
    wordEl.textContent = words[type] || words.info;
    bandEl.append(iconEl, wordEl);

    // El mensaje se inserta como TEXTO (nunca como HTML) para evitar XSS
    const textEl = document.createElement('span');
    textEl.className = 'toast-text';
    textEl.textContent = message;

    const closeEl = document.createElement('button');
    closeEl.type = 'button';
    closeEl.className = 'toast-close';
    closeEl.setAttribute('aria-label', en ? 'Close' : 'Cerrar');
    closeEl.innerHTML = svg('<path d="M18 6 6 18M6 6l12 12"/>');

    bandEl.append(closeEl);
    toast.append(bandEl, textEl);
    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toast.classList.add('is-leaving');
        setTimeout(() => toast.remove(), 220);
    });

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.classList.add('is-leaving');
            setTimeout(() => toast.remove(), 220);
        }
    }, duration);
}

// ==============================================================================
// OPTIMIZACIÓN DE LLAMADAS API Y DEDUPLICACIÓN (v1.3.0)
// ==============================================================================
const inFlightRequests = new Map();

/**
 * Wrapper de peticiones fetch con deduplicación automática de peticiones GET en vuelo.
 * Si una petición GET a la misma URL ya está pendiente, reutiliza la misma Promesa.
 */
window.apiFetch = function(url, options = {}) {
    const method = (options.method || 'GET').toUpperCase();

    // Solo deduplicamos peticiones GET idempotentes
    if (method === 'GET') {
        const cacheKey = url;
        if (inFlightRequests.has(cacheKey)) {
            return inFlightRequests.get(cacheKey);
        }

        const promise = fetch(url, options)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .finally(() => {
                inFlightRequests.delete(cacheKey);
            });

        inFlightRequests.set(cacheKey, promise);
        return promise;
    }

    // Para POST, PUT, DELETE se ejecuta normalmente con retorno JSON
    return fetch(url, options).then(response => {
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
    });
};

/**
 * Función de debounce con soporte de AbortController para búsquedas y filtros en tiempo real
 */
window.debounce = function(fn, delay = 300) {
    let timer = null;
    let abortController = null;

    return function(...args) {
        if (timer) clearTimeout(timer);
        if (abortController) abortController.abort();

        abortController = new AbortController();
        const signal = abortController.signal;

        return new Promise((resolve, reject) => {
            timer = setTimeout(async () => {
                try {
                    const result = await fn(...args, { signal });
                    resolve(result);
                } catch (err) {
                    if (err.name !== 'AbortError') {
                        reject(err);
                    }
                }
            }, delay);
        });
    };
};

// Los formularios POST comparten estado y bloqueo; el submitter conserva su valor.
document.addEventListener('submit', event => {
    const form = event.target;
    if (event.defaultPrevented || form.method.toLowerCase() !== 'post') return;
    if (form.dataset.submitting) { event.preventDefault(); return; }
    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    let status = form.querySelector('.form-status');
    if (!status) {
        status = document.createElement('p'); status.className = 'form-status';
        status.setAttribute('role', 'status'); form.append(status);
    }
    status.textContent = 'Enviando…';
    // Deferir disabled para no excluir el campo submit antes de serializar el formulario.
    setTimeout(() => {
        form.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(button => {
            if (!button.disabled) { button.dataset.submitDisabled = 'true'; button.disabled = true; }
        });
    }, 0);
});
window.addEventListener('pageshow', () => {
    document.querySelectorAll('form[data-submitting]').forEach(form => {
        delete form.dataset.submitting; form.removeAttribute('aria-busy');
        form.querySelectorAll('[data-submit-disabled]').forEach(button => {
            button.disabled = false; delete button.dataset.submitDisabled;
        });
        form.querySelector('.form-status')?.remove();
    });
});
