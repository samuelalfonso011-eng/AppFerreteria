/**
 * Gráficos del dashboard administrativo (Chart.js). Sin código inline: la URL de datos
 * llega por data-metrics-url y los colores se leen de los tokens CSS del tema activo.
 */
(function () {
    'use strict';

    var script = document.currentScript;
    var url = script && script.getAttribute('data-metrics-url');
    if (!url || typeof Chart === 'undefined') { return; }

    function token(name, fallback) {
        var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
        return v || fallback;
    }

    function fmtCOP(n) {
        return '$' + Math.round(n).toLocaleString('es-CO');
    }

    fetch(url, { headers: { 'Accept': 'application/json' }, credentials: 'same-origin' })
        .then(function (r) { if (!r.ok) { throw new Error('HTTP ' + r.status); } return r.json(); })
        .then(function (d) {
            var amber = token('--amber', '#F59E0B');
            var slate = token('--slate-700', '#334155');
            var safety = token('--safety', '#EA580C');
            var muted = token('--muted', '#475569');
            var grid = token('--border', '#E2E8F0');

            Chart.defaults.color = muted;
            Chart.defaults.font.family = token('--font-family', 'sans-serif');
            var common = { responsive: true, maintainAspectRatio: false };

            new Chart(document.getElementById('salesTrendChart'), {
                type: 'line',
                data: {
                    labels: d.sales_trend.map(function (p) { return p.date; }),
                    datasets: [{
                        label: 'Ventas',
                        data: d.sales_trend.map(function (p) { return p.total; }),
                        borderColor: amber, backgroundColor: amber + '33', fill: true, tension: 0.3, pointRadius: 3
                    }]
                },
                options: Object.assign({}, common, {
                    plugins: { legend: { display: false }, tooltip: { callbacks: { label: function (c) { return fmtCOP(c.parsed.y); } } } },
                    scales: { y: { beginAtZero: true, grid: { color: grid }, ticks: { callback: fmtCOP } }, x: { grid: { display: false } } }
                })
            });

            new Chart(document.getElementById('topProductsChart'), {
                type: 'bar',
                data: {
                    labels: d.top_products.map(function (p) { return p.name; }),
                    datasets: [{ label: 'Unidades', data: d.top_products.map(function (p) { return p.units; }), backgroundColor: amber }]
                },
                options: Object.assign({}, common, {
                    indexAxis: 'y',
                    plugins: { legend: { display: false } },
                    scales: { x: { beginAtZero: true, grid: { color: grid }, ticks: { precision: 0 } }, y: { grid: { display: false } } }
                })
            });

            var statusLabels = Object.keys(d.orders_by_status);
            new Chart(document.getElementById('orderStatusChart'), {
                type: 'doughnut',
                data: {
                    labels: statusLabels,
                    datasets: [{
                        data: statusLabels.map(function (k) { return d.orders_by_status[k]; }),
                        backgroundColor: [amber, slate, '#64748B', '#15803D', safety],
                        borderColor: token('--panel', '#FFFFFF'), borderWidth: 2
                    }]
                },
                options: Object.assign({}, common, { plugins: { legend: { position: 'bottom' } } })
            });
        })
        .catch(function () {
            document.querySelectorAll('.dash-chart-box').forEach(function (b) {
                b.setAttribute('data-error', 'No se pudieron cargar los datos del gráfico.');
            });
        });
})();
