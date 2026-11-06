/**
 * AI Concierge JavaScript
 */

document.addEventListener('DOMContentLoaded', function() {
    initializeAIChat();
});

/**
 * Initialize AI chat
 */
function initializeAIChat() {
    const chatInput = document.getElementById('chat-input');
    const sendButton = document.getElementById('send-button');
    
    if (!chatInput) return;
    
    // Send message on Enter key
    chatInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    if (sendButton) {
        sendButton.addEventListener('click', sendMessage);
    }
}

/**
 * Send message to AI
 */
function sendMessage() {
    const input = document.getElementById('chat-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Add user message to chat
    addMessageToChat('user', message);
    input.value = '';
    
    // Show typing indicator
    showTypingIndicator();
    
    // Send to API
    ThysiaOps.fetchJSON('/ai-concierge/api/chat', {
        method: 'POST',
        body: JSON.stringify({ message: message })
    })
    .then(data => {
        hideTypingIndicator();
        if (data.success) {
            addMessageToChat('ai', data.response);
        } else {
            addMessageToChat('ai', 'Sorry, I encountered an error. Please try again.');
        }
    })
    .catch(error => {
        hideTypingIndicator();
        addMessageToChat('ai', 'Sorry, I\'m having trouble connecting. Please try again later.');
    });
}

/**
 * Add message to chat
 */
function addMessageToChat(sender, message) {
    const messagesDiv = document.getElementById('chat-messages');
    if (!messagesDiv) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${sender} mb-3`;
    
    const senderLabel = sender === 'user' ? 'You' : 'AI Assistant';
    const messageClass = sender === 'user' ? 'bg-primary text-white' : 'bg-light';
    
    messageDiv.innerHTML = `
        <div class="d-flex ${sender === 'user' ? 'justify-content-end' : ''}">
            <div class="message-bubble ${messageClass} p-3 rounded" style="max-width: 70%;">
                <small class="d-block mb-1"><strong>${senderLabel}</strong></small>
                <div>${escapeHtml(message)}</div>
            </div>
        </div>
    `;
    
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

/**
 * Show typing indicator
 */
function showTypingIndicator() {
    const messagesDiv = document.getElementById('chat-messages');
    if (!messagesDiv) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'text-muted mb-3';
    indicator.innerHTML = '<em>AI is typing...</em>';
    
    messagesDiv.appendChild(indicator);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

/**
 * Hide typing indicator
 */
function hideTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Clear chat history
 */
function clearChat() {
    if (confirm('Are you sure you want to clear the chat history?')) {
        const messagesDiv = document.getElementById('chat-messages');
        if (messagesDiv) {
            messagesDiv.innerHTML = '<p class="text-muted">Ask me anything about resort operations...</p>';
        }
    }
}
