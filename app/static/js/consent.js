/** Preferencias por finalidad. No hay rastreadores instalados en esta versión. */
(function () {
    'use strict';
    const KEY = 'cookie_consent';
    const VERSION = '2026-11-13';
    const MAX_AGE = 365 * 24 * 60 * 60 * 1000;
    let preference = null;
    try {
        const value = JSON.parse(localStorage.getItem(KEY));
        const age = Date.now() - Date.parse(value?.updatedAt);
        if (value?.version === VERSION && value.necessary === true &&
            typeof value.analytics === 'boolean' && typeof value.marketing === 'boolean' &&
            age >= 0 && age < MAX_AGE) preference = value;
    } catch (_) { /* Sin almacenamiento o con formato antiguo: solicitar una elección nueva. */ }

    // Las futuras integraciones deben consultar allows() antes de iniciar cualquier rastreo.
    window.cookieConsent = Object.freeze({
        allows: category => category === 'necessary' ||
            (['analytics', 'marketing'].includes(category) && preference?.[category] === true),
        getPreference: () => preference ? { ...preference } : null
    });

    document.addEventListener('DOMContentLoaded', () => {
        const banner = document.getElementById('cookieConsentBanner');
        if (!banner) return;
        const analytics = document.getElementById('cookieAnalytics');
        const marketing = document.getElementById('cookieMarketing');
        const reopen = document.getElementById('cookiePreferences');
        const message = document.getElementById('consentStatus');
        const show = () => {
            analytics.checked = preference?.analytics === true;
            marketing.checked = preference?.marketing === true;
            banner.hidden = false;
        };
        const save = (allowAnalytics, allowMarketing) => {
            preference = { version: VERSION, necessary: true, analytics: allowAnalytics,
                marketing: allowMarketing, updatedAt: new Date().toISOString() };
            try {
                localStorage.setItem(KEY, JSON.stringify(preference));
                message.textContent = 'Preferencias guardadas. Puedes cambiarlas desde el pie de página.';
            } catch (_) {
                message.textContent = 'Preferencias aplicadas a esta página. El navegador no permite guardarlas.';
            }
            // Eliminar la antigua cookie redundante; la preferencia nueva se guarda en localStorage.
            document.cookie = 'cookie_consent=; path=/; max-age=0; SameSite=Lax';
            banner.hidden = true;
            reopen.focus({ preventScroll: true });
            window.dispatchEvent(new CustomEvent('cookieconsentchange', { detail: { ...preference } }));
        };
        document.getElementById('cookieAcceptEssential').addEventListener('click', () => save(false, false));
        document.getElementById('cookieAcceptAll').addEventListener('click', () => save(true, true));
        document.getElementById('cookieSavePreferences').addEventListener('click', () => save(analytics.checked, marketing.checked));
        reopen.addEventListener('click', () => { show(); banner.focus(); });
        if (!preference) show();
    });
})();
