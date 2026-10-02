/**
 * Analytics JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    if (typeof Chart !== 'undefined') {
        loadAnalyticsData();
    }
});

/**
 * Load analytics data
 */
function loadAnalyticsData() {
    Promise.all([
        ThysiaOps.fetchJSON('/analytics/api/revenue?period=month'),
        ThysiaOps.fetchJSON('/analytics/api/occupancy')
    ])
    .then(([revenueData, occupancyData]) => {
        renderRevenueChart(revenueData.data);
        renderOccupancyChart(occupancyData.data);
    })
    .catch(error => {
        console.error('Error loading analytics:', error);
    });
}

/**
 * Render revenue chart
 */
function renderRevenueChart(data) {
    const ctx = document.getElementById('revenueChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.daily_breakdown.map(d => d.date),
            datasets: [{
                label: 'Revenue',
                data: data.daily_breakdown.map(d => d.revenue),
                borderColor: 'rgb(13, 110, 253)',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Revenue: ' + ThysiaOps.formatCurrency(context.parsed.y);
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

/**
 * Render occupancy chart
 */
function renderOccupancyChart(data) {
    const ctx = document.getElementById('occupancyChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.daily_occupancy.map(d => d.date),
            datasets: [{
                label: 'Occupancy Rate',
                data: data.daily_occupancy.map(d => d.rate),
                backgroundColor: 'rgba(25, 135, 84, 0.5)',
                borderColor: 'rgb(25, 135, 84)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Export report
 */
function exportReport(format) {
    ThysiaOps.showToast('Exporting report...', 'info');
    
    // Implementation for export
    window.location.href = `/analytics/export?format=${format}`;
}
