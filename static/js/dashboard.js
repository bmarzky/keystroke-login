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

        const currentDwellMs = Array.isArray(current.dwell) ? current.dwell.map((v) => Math.round(v * 1000)) : [];
        const prevDwellMs = Array.isArray(prev.dwell) ? prev.dwell.map((v) => Math.round(v * 1000)) : [];
        const currentFlightMs = Array.isArray(current.flight) ? current.flight.map((v) => Math.round(v * 1000)) : [];
        const prevFlightMs = Array.isArray(prev.flight) ? prev.flight.map((v) => Math.round(v * 1000)) : [];

        const ctx = chartCanvas.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: currentDwellMs.map((_, index) => `K${index + 1}`),
                datasets: [
                    {
                        label: 'Dwell (Current)',
                        data: currentDwellMs,
                        borderColor: '#000',
                        backgroundColor: '#000',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Dwell (History)',
                        data: prevDwellMs,
                        borderColor: '#000',
                        borderWidth: 1,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Flight (Current)',
                        data: currentFlightMs,
                        borderColor: '#000',
                        backgroundColor: '#000',
                        borderWidth: 2,
                        pointRadius: 0,
                        fill: false,
                        tension: 0.3,
                    },
                    {
                        label: 'Flight (History)',
                        data: prevFlightMs,
                        borderColor: '#000',
                        borderWidth: 1,
                        borderDash: [5, 5],
                        pointRadius: 0,
                        fill: false,
                        tension: 0.3,
                    }
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
