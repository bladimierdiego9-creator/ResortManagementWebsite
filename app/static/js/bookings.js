/**
 * Bookings JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeBookingForm();
    initializeAvailabilityChecker();
});

/**
 * Initialize booking form
 */
function initializeBookingForm() {
    const bookingForm = document.getElementById('booking-form');
    if (!bookingForm) return;
    
    bookingForm.addEventListener('submit', function(e) {
        const button = bookingForm.querySelector('button[type="submit"]');
        ThysiaOps.showLoading(button);
    });
}

/**
 * Initialize availability checker
 */
function initializeAvailabilityChecker() {
    const facilitySelect = document.querySelector('select[name="facility_id"]');
    const checkInInput = document.querySelector('input[name="check_in_date"]');
    const checkOutInput = document.querySelector('input[name="check_out_date"]');
    
    if (!facilitySelect || !checkInInput || !checkOutInput) return;
    
    const checkAvailability = ThysiaOps.debounce(function() {
        const facilityId = facilitySelect.value;
        const checkIn = checkInInput.value;
        const checkOut = checkOutInput.value;
        
        if (!facilityId || !checkIn || !checkOut) return;
        
        ThysiaOps.fetchJSON('/bookings/api/check-availability', {
            method: 'POST',
            body: JSON.stringify({
                facility_id: facilityId,
                check_in_date: checkIn,
                check_out_date: checkOut
            })
        })
        .then(data => {
            if (data.success) {
                showAvailabilityStatus(data.available);
            }
        });
    }, 500);
    
    checkInInput.addEventListener('change', checkAvailability);
    checkOutInput.addEventListener('change', checkAvailability);
    facilitySelect.addEventListener('change', checkAvailability);
}

/**
 * Show availability status
 */
function showAvailabilityStatus(available) {
    const statusDiv = document.getElementById('availability-status');
    if (!statusDiv) {
        const div = document.createElement('div');
        div.id = 'availability-status';
        div.className = 'alert mt-2';
        document.querySelector('select[name="facility_id"]').parentElement.appendChild(div);
    }
    
    const statusElement = document.getElementById('availability-status');
    if (available) {
        statusElement.className = 'alert alert-success mt-2';
        statusElement.textContent = '✓ Facility is available for selected dates';
    } else {
        statusElement.className = 'alert alert-warning mt-2';
        statusElement.textContent = '⚠ Facility is not available for selected dates';
    }
}

/**
 * Calculate booking total
 */
function calculateBookingTotal() {
    const checkIn = document.querySelector('input[name="check_in_date"]').value;
    const checkOut = document.querySelector('input[name="check_out_date"]').value;
    const facilitySelect = document.querySelector('select[name="facility_id"]');
    
    if (!checkIn || !checkOut || !facilitySelect) return;
    
    const nights = Math.ceil((new Date(checkOut) - new Date(checkIn)) / (1000 * 60 * 60 * 24));
    const pricePerNight = parseFloat(facilitySelect.selectedOptions[0].getAttribute('data-price') || 0);
    const total = nights * pricePerNight;
    
    const totalElement = document.getElementById('booking-total');
    if (totalElement) {
        totalElement.textContent = `Total: ${ThysiaOps.formatCurrency(total)} (${nights} nights)`;
    }
}
