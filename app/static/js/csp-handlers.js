/**
 * Manejadores delegados compatibles con Content-Security-Policy (sin atributos on* inline).
 * Funcionan también sobre contenido inyectado por la navegación SPA.
 *
 *   <form data-confirm="¿Seguro?">            confirma antes de enviar
 *   <select data-autosubmit>                  envía el formulario al cambiar
 *   <button data-print>                       abre el diálogo de impresión
 *   <img data-img-fallback="/ruta.svg">       imagen alternativa si falla la carga
 */
(function () {
    'use strict';

    document.addEventListener('submit', function (e) {
        var form = e.target;
        if (form && form.matches && form.matches('form[data-confirm]')) {
            if (!window.confirm(form.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        }
    });

    document.addEventListener('change', function (e) {
        var el = e.target;
        if (el && el.matches && el.matches('[data-autosubmit]') && el.form) {
            el.form.requestSubmit();
        }
    });

    document.addEventListener('click', function (e) {
        var btn = e.target.closest && e.target.closest('[data-print]');
        if (btn) {
            e.preventDefault();
            window.print();
        }
    });

    function applyFallback(img) {
        var fallback = img.getAttribute('data-img-fallback');
        if (fallback && img.getAttribute('src') !== fallback) {
            img.removeAttribute('data-img-fallback'); // evita bucles si el fallback también falla
            img.src = fallback;
        }
    }

    // 'error' no burbujea: se captura en la fase de captura
    document.addEventListener('error', function (e) {
        if (e.target && e.target.tagName === 'IMG') {
            applyFallback(e.target);
        }
    }, true);

    // Imágenes que fallaron antes de registrar el listener
    document.addEventListener('DOMContentLoaded', function () {
        document.querySelectorAll('img[data-img-fallback]').forEach(function (img) {
            if (img.complete && img.naturalWidth === 0) {
                applyFallback(img);
            }
        });
    });
})();
