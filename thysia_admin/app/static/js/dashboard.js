/**
 * Dashboard JavaScript
 */

// Update dashboard stats periodically
let statsUpdateInterval;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize dashboard
    initializeDashboard();
    
    // Start auto-refresh
    startStatsAutoRefresh();
});

/**
 * Initialize dashboard
 */
function initializeDashboard() {
    // Load initial stats
    updateDashboardStats();
    
    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }
}

/**
 * Update dashboard statistics
 */
function updateDashboardStats() {
    fetch('/dashboard/api/stats')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                updateStatsDisplay(data.data);
            }
        })
        .catch(error => console.error('Error updating stats:', error));
}

/**
 * Update stats display
 */
function updateStatsDisplay(stats) {
    // Update occupancy rate
    const occupancyElement = document.querySelector('[data-stat="occupancy_rate"]');
    if (occupancyElement) {
        occupancyElement.textContent = stats.occupancy_rate + '%';
    }
    
    // Update total bookings
    const bookingsElement = document.querySelector('[data-stat="total_bookings"]');
    if (bookingsElement) {
        bookingsElement.textContent = stats.total_bookings;
    }
    
    // Update revenue
    const revenueElement = document.querySelector('[data-stat="total_revenue"]');
    if (revenueElement) {
        revenueElement.textContent = ThysiaOps.formatCurrency(stats.total_revenue);
    }
}

/**
 * Start auto-refresh of stats
 */
function startStatsAutoRefresh(interval = 60000) {
    if (statsUpdateInterval) {
        clearInterval(statsUpdateInterval);
    }
    
    statsUpdateInterval = setInterval(updateDashboardStats, interval);
}

/**
 * Stop auto-refresh
 */
function stopStatsAutoRefresh() {
    if (statsUpdateInterval) {
        clearInterval(statsUpdateInterval);
        statsUpdateInterval = null;
    }
}

/**
 * Initialize charts
 */
function initializeCharts() {
    // Revenue chart
    const revenueCtx = document.getElementById('revenueChart');
    if (revenueCtx) {
        new Chart(revenueCtx, {
            type: 'line',
            data: {
                labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                datasets: [{
                    label: 'Revenue',
                    data: [12000, 19000, 15000, 25000, 22000, 30000],
                    borderColor: 'rgb(13, 110, 253)',
                    tension: 0.1
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
    
    // Occupancy chart
    const occupancyCtx = document.getElementById('occupancyChart');
    if (occupancyCtx) {
        new Chart(occupancyCtx, {
            type: 'bar',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [{
                    label: 'Occupancy %',
                    data: [65, 70, 80, 75, 90, 95, 85],
                    backgroundColor: 'rgba(13, 110, 253, 0.5)'
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: false
                    }
                }
            }
        });
    }
}

// Clean up on page unload
window.addEventListener('beforeunload', function() {
    stopStatsAutoRefresh();
});
