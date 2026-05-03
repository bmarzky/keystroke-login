/*
 * Dashboard page behavior.
 * Menangani pembacaan data keystroke dari DOM dan pembuatan grafik Chart.js.
 */

const DashboardPage = (() => {
    const parseDashboardData = () => {
        const dataContainer = document.getElementById('dashboard-data');
        if (!dataContainer) return { current: { dwell: [], flight: [] }, prev: { dwell: [], flight: [] } };

        try {
            const current = JSON.parse(dataContainer.dataset.current || '{}');
            const prev = JSON.parse(dataContainer.dataset.prev || '{}');
            return { current, prev };
        } catch (error) {
            console.error('Gagal membaca data dashboard:', error);
            return { current: { dwell: [], flight: [] }, prev: { dwell: [], flight: [] } };
        }
    };

    const buildChart = (current, prev) => {
        const chartCanvas = document.getElementById('keystrokeChart');
        if (!chartCanvas || typeof Chart === 'undefined') return;

        const currentDwellMs = Array.isArray(current.dwell) ? current.dwell.map((value) => Math.round(value * 1000)) : [];
        const prevDwellMs = Array.isArray(prev.dwell) ? prev.dwell.map((value) => Math.round(value * 1000)) : [];

        const ctx = chartCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: currentDwellMs.map((_, index) => `K${index + 1}`),
                datasets: [
                    {
                        label: 'Dwell Terbaru (ms)',
                        data: currentDwellMs,
                        borderColor: '#000',
                        backgroundColor: '#000',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.2,
                    },
                    {
                        label: 'Dwell Sebelumnya (ms)',
                        data: prevDwellMs,
                        borderColor: '#999',
                        backgroundColor: '#999',
                        borderWidth: 2,
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.2,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            boxWidth: 12,
                            font: { weight: 'bold' },
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => `${context.raw} ms`,
                        },
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        title: {
                            display: true,
                            text: 'Durasi (Milidetik)',
                        },
                    },
                },
            },
        });
    };

    const init = () => {
        const { current, prev } = parseDashboardData();
        buildChart(current, prev);
    };

    return { init };
})();

window.addEventListener('DOMContentLoaded', DashboardPage.init);
