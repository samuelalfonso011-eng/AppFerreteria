// Scripts principales de la ferretería web (v1.1.0)
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

// Inicializador general de la aplicación
function initApp() {
    initFlashAlerts();
    initThemeToggle();
    initCookieConsent();
    initBackToTop();
    initMobileMenu();
    initScrollReveal();
}

// Cierre suave de alertas de Flask
function initFlashAlerts() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
            alert.style.opacity = '0';
            alert.style.transform = 'translateY(-10px)';
            setTimeout(() => alert.remove(), 400);
        }, 5000);
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

// Banner de Consentimiento de Cookies
function initCookieConsent() {
    const banner = document.getElementById('cookieConsentBanner');
    if (!banner) return;

    try {
        const consent = localStorage.getItem('cookie_consent');
        if (!consent) {
            banner.style.display = 'block';
        }
    } catch(e) {
        banner.style.display = 'block';
    }

    const acceptAll = document.getElementById('cookieAcceptAll');
    const acceptEssential = document.getElementById('cookieAcceptEssential');

    function saveConsent(type) {
        try {
            localStorage.setItem('cookie_consent', type);
            document.cookie = "cookie_consent=" + type + "; path=/; max-age=31536000; SameSite=Lax";
        } catch(e) {}
        banner.style.display = 'none';
    }

    if (acceptAll && !acceptAll.dataset.bound) {
        acceptAll.dataset.bound = "true";
        acceptAll.addEventListener('click', function() { saveConsent('all'); });
    }
    if (acceptEssential && !acceptEssential.dataset.bound) {
        acceptEssential.dataset.bound = "true";
        acceptEssential.addEventListener('click', function() { saveConsent('essential'); });
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
                behavior: 'smooth'
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
    if (!('IntersectionObserver' in window)) return;

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

// Sistema de Notificaciones Toast Flotantes
function showToast(message, type = 'info', duration = 4000) {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;

    const icons = {
        success: '✅',
        danger: '❌',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
        <span class="toast-text">${message}</span>
        <button type="button" class="toast-close" aria-label="Cerrar">&times;</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    closeBtn.addEventListener('click', () => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(50px)';
        setTimeout(() => toast.remove(), 300);
    });

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(50px)';
            setTimeout(() => toast.remove(), 300);
        }
    }, duration);
}

// Exportar para recarga SPA
window.initPageEnhancements = function() {
    initScrollReveal();
    initFlashAlerts();
    initBackToTop();
};
