/**
 * Calendar JavaScript
 */

// Initialize calendar when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeCalendar();
});

/**
 * Initialize FullCalendar
 */
function initializeCalendar() {
    const calendarEl = document.getElementById('calendar');
    if (!calendarEl) return;
    
    const calendar = new FullCalendar.Calendar(calendarEl, {
        initialView: 'dayGridMonth',
        headerToolbar: {
            left: 'prev,next today',
            center: 'title',
            right: 'dayGridMonth,timeGridWeek,timeGridDay'
        },
        events: '/calendar/api/events',
        eventClick: function(info) {
            showBookingDetails(info.event);
        },
        eventDidMount: function(info) {
            // Add tooltip
            info.el.title = `${info.event.title}\nStatus: ${info.event.extendedProps.status}`;
        },
        height: 'auto',
        expandRows: true
    });
    
    calendar.render();
}

/**
 * Show booking details in modal
 */
function showBookingDetails(event) {
    const bookingId = event.id;
    window.location.href = `/bookings/${bookingId}`;
}

/**
 * Filter calendar by status
 */
function filterCalendarByStatus(status) {
    const calendar = FullCalendar.Calendar.getInstance(document.getElementById('calendar'));
    if (!calendar) return;
    
    calendar.refetchEvents();
}
