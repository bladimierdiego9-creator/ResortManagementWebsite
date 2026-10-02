/* ============================================================
   A&D THYSIA ADMIN CONSOLE — MAIN JS
   ============================================================ */

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-analytics.js";

const firebaseConfig = {
  apiKey: "AIzaSyB8YnwxhoIDAtR7-nlnR3FIa9ZmrTdGePM",
  authDomain: "aanddthysia.firebaseapp.com",
  projectId: "aanddthysia",
  storageBucket: "aanddthysia.firebasestorage.app",
  messagingSenderId: "884057388304",
  appId: "1:884057388304:web:1f7e446fdadcee2f856195",
  measurementId: "G-7RPZKYWSQ5"
};

const firebaseApp = initializeApp(firebaseConfig);
const analytics = getAnalytics(firebaseApp);

console.log("Firebase initialized:", firebaseApp.name);

// ── SIDEBAR TOGGLE ──────────────────────────────────────────
function toggleSidebar() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebarOverlay');
  if (sidebar) sidebar.classList.toggle('open');
  if (overlay) overlay.classList.toggle('open');
}
window.toggleSidebar = toggleSidebar;

// ── USER DROPDOWN ───────────────────────────────────────────
function toggleUserMenu() {
  const dropdown = document.getElementById('userDropdown');
  if (dropdown) dropdown.classList.toggle('open');
}
window.toggleUserMenu = toggleUserMenu;

// Close user dropdown on outside click
document.addEventListener('click', function (e) {
  const dropdown = document.getElementById('userDropdown');
  const btn = document.querySelector('.user-menu-btn');
  if (dropdown && dropdown.classList.contains('open')) {
    if (!dropdown.contains(e.target) && e.target !== btn) {
      dropdown.classList.remove('open');
    }
  }
});

// ── MODAL HELPERS ───────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add('open');
}
window.openModal = openModal;

function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove('open');
}
window.closeModal = closeModal;

// Close modal on overlay click
document.addEventListener('click', function (e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// Close modal on Escape key
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(function (m) {
      m.classList.remove('open');
    });
  }
});

// ── TAB SWITCHING ──────────────────────────────────────────
function switchTab(tabId, groupId) {
  // Hide all tab content in the group
  const group = document.getElementById(groupId);
  if (!group) return;
  group.querySelectorAll('.tab-content').forEach(function (el) {
    el.style.display = 'none';
  });
  // Deactivate all tab buttons
  document.querySelectorAll('[data-tabgroup="' + groupId + '"]').forEach(function (btn) {
    btn.classList.remove('active');
  });
  // Show target tab content
  const target = document.getElementById(tabId);
  if (target) target.style.display = 'block';
  // Activate the clicked tab
  const activeBtn = document.querySelector('[data-tab="' + tabId + '"]');
  if (activeBtn) activeBtn.classList.add('active');
}

// ── AUTO-HIDE FLASH MESSAGES ────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(function (flash) {
    setTimeout(function () {
      flash.style.opacity = '0';
      flash.style.transition = 'opacity 0.4s';
      setTimeout(function () { flash.remove(); }, 400);
    }, 4000);
  });
});

// ── CUSTOM CONFIRMATION MODAL ───────────────────────────────
let confirmCallback = null;

function showConfirmModal(message, onConfirm) {
  const modal = document.getElementById('confirmModal');
  const messageEl = document.getElementById('confirmMessage');
  if (modal && messageEl) {
    messageEl.textContent = message;
    modal.classList.add('open');
    confirmCallback = onConfirm;
  }
}
window.showConfirmModal = showConfirmModal;

function confirmAction() {
  const modal = document.getElementById('confirmModal');
  if (modal) modal.classList.remove('open');
  if (confirmCallback) {
    confirmCallback();
    confirmCallback = null;
  }
}
window.confirmAction = confirmAction;

function cancelAction() {
  const modal = document.getElementById('confirmModal');
  if (modal) modal.classList.remove('open');
  confirmCallback = null;
}
window.cancelAction = cancelAction;

// ── LOGOUT MODAL ────────────────────────────────────────────
function showLogoutModal() {
  const modal = document.getElementById('logoutModal');
  if (modal) modal.classList.add('open');
}
window.showLogoutModal = showLogoutModal;

function confirmLogout() {
  window.location.href = '/auth/logout';
}
window.confirmLogout = confirmLogout;

// ── CONFIRM DELETES ─────────────────────────────────────────
document.addEventListener('submit', function (e) {
  const form = e.target;
  if (form.dataset.confirm) {
    e.preventDefault();
    showConfirmModal(form.dataset.confirm, function() {
      // Remove the confirm attribute to avoid infinite loop
      form.removeAttribute('data-confirm');
      form.submit();
    });
  }
});

// ── EXPOSE CHART HELPERS GLOBALLY ──────────────────────────
// main.js loads as a module, so these must be attached to window
// for inline template scripts (overview/analytics) to call them.
window.renderSparkline = renderSparkline;
window.renderBookingChart = renderBookingChart;
window.renderDoughnutChart = renderDoughnutChart;
window.renderLineChart = renderLineChart;;

// ── SPARKLINE CHART ─────────────────────────────────────────
function renderSparkline(canvasId, data, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  new Chart(canvas, {
    type: 'line',
    data: {
      labels: data.map(function (_, i) { return i; }),
      datasets: [{
        data: data,
        borderColor: color || '#1a7a4a',
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        backgroundColor: (color || '#1a7a4a') + '22',
        tension: 0.4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      scales: { x: { display: false }, y: { display: false } },
      elements: { line: { borderCapStyle: 'round' } }
    }
  });
}

// ── BOOKING TREND CHART ─────────────────────────────────────
function renderBookingChart(canvasId, labels, data) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Bookings',
        data: data,
        backgroundColor: '#1a7a4a',
        borderRadius: 5,
        borderSkipped: false,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#111827',
          titleFont: { size: 12 },
          bodyFont: { size: 12 },
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 }, maxTicksLimit: 8, color: '#9ca3af' }
        },
        y: {
          grid: { color: '#f0f2f5' },
          ticks: { font: { size: 11 }, stepSize: 1, color: '#9ca3af' },
          beginAtZero: true,
        }
      }
    }
  });
}

// ── DOUGHNUT CHART ──────────────────────────────────────────
function renderDoughnutChart(canvasId, labels, data, colors) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: data,
        backgroundColor: colors || ['#1a7a4a', '#c9a44e', '#dc2626'],
        borderWidth: 3,
        borderColor: '#fff',
        hoverOffset: 4,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: '70%',
      plugins: {
        legend: {
          position: 'bottom',
          labels: { font: { size: 12 }, padding: 12, usePointStyle: true }
        },
        tooltip: {
          backgroundColor: '#111827',
          titleFont: { size: 12 },
          bodyFont: { size: 12 },
        }
      }
    }
  });
}

// ── LINE CHART ──────────────────────────────────────────────
function renderLineChart(canvasId, labels, datasets) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || typeof Chart === 'undefined') return;
  new Chart(canvas, {
    type: 'line',
    data: { labels: labels, datasets: datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: true, position: 'top', labels: { font: { size: 12 } } },
        tooltip: { backgroundColor: '#111827' }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { font: { size: 11 }, color: '#9ca3af', maxTicksLimit: 10 }
        },
        y: {
          grid: { color: '#f0f2f5' },
          ticks: { font: { size: 11 }, color: '#9ca3af' },
          beginAtZero: true
        }
      }
    }
  });
}
