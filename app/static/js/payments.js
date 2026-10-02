/**
 * Payments JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    initializePaymentForm();
});

/**
 * Initialize payment form
 */
function initializePaymentForm() {
    const paymentForm = document.getElementById('payment-form');
    if (!paymentForm) return;
    
    paymentForm.addEventListener('submit', function(e) {
        const paymentMethod = document.querySelector('select[name="payment_method"]').value;
        
        if (paymentMethod === 'credit_card') {
            e.preventDefault();
            processCardPayment();
        } else {
            const button = paymentForm.querySelector('button[type="submit"]');
            ThysiaOps.showLoading(button);
        }
    });
}

/**
 * Process card payment
 */
function processCardPayment() {
    const button = document.querySelector('#payment-form button[type="submit"]');
    ThysiaOps.showLoading(button);
    
    // In production, integrate with Stripe or other payment gateway
    ThysiaOps.showToast('Card payment processing not yet implemented', 'info');
    ThysiaOps.hideLoading(button);
}

/**
 * Calculate payment summary
 */
function updatePaymentSummary() {
    const amount = parseFloat(document.querySelector('input[name="amount"]').value || 0);
    const summaryElement = document.getElementById('payment-summary');
    
    if (summaryElement) {
        summaryElement.innerHTML = `
            <div class="card">
                <div class="card-body">
                    <h5>Payment Summary</h5>
                    <p>Amount: ${ThysiaOps.formatCurrency(amount)}</p>
                </div>
            </div>
        `;
    }
}
