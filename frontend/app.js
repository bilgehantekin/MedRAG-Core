/**
 * Medical Chatbot - Frontend
 */

const state = {
    messages: [],
    isLoading: false,
    apiUrl: 'http://localhost:8000'
};

const chatContainer = document.getElementById('chatContainer');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    messageInput.focus();
});

// Quick message
function sendQuickMessage(msg) {
    messageInput.value = msg;
    sendMessage();
}

// Handle Enter key
function handleKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Auto resize textarea
function autoResize(textarea) {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// Hide welcome
function hideWelcome() {
    const welcome = chatContainer.querySelector('.welcome-message');
    if (welcome) welcome.remove();
}

// Scroll to bottom
function scrollToBottom() {
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

// Format message
function formatMessage(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/^### (.*$)/gm, '<h4>$1</h4>')
        .replace(/^## (.*$)/gm, '<h3>$1</h3>')
        .replace(/^[•\-\*] (.*$)/gm, '<div class="list-item">• $1</div>')
        .replace(/^(\d+)\. (.*$)/gm, '<div class="list-item">$1. $2</div>')
        .replace(/^(⚠️.*?)$/gm, '<div class="warning-line">$1</div>')
        .replace(/\n(?!<)/g, '<br>')
        .replace(/<br>(<div)/g, '$1')
        .replace(/(<\/div>)<br>/g, '$1');
}

// Add user message
function addUserMessage(content) {
    hideWelcome();
    
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `
        <div class="message-avatar">👤</div>
        <div class="message-content">
            <div class="message-text">${formatMessage(content)}</div>
        </div>
    `;
    
    chatContainer.appendChild(div);
    scrollToBottom();
    state.messages.push({ role: 'user', content });
}

// Add assistant message
function addAssistantMessage(content, isEmergency = false) {
    hideWelcome();
    
    const div = document.createElement('div');
    div.className = 'message assistant' + (isEmergency ? ' emergency' : '');
    div.innerHTML = `
        <div class="message-avatar">🏥</div>
        <div class="message-content">
            <div class="message-text">${formatMessage(content)}</div>
            ${!isEmergency ? '<div class="message-disclaimer">⚠️ Bu bilgiler eğitim amaçlıdır, tıbbi tavsiye değildir.</div>' : ''}
        </div>
    `;
    
    chatContainer.appendChild(div);
    scrollToBottom();
    state.messages.push({ role: 'assistant', content });
}

// Add loading message
function addLoadingMessage() {
    hideWelcome();
    
    const div = document.createElement('div');
    div.className = 'message assistant loading-msg';
    div.innerHTML = `
        <div class="message-avatar">🏥</div>
        <div class="message-content">
            <div class="message-text">
                <div class="loading-dots">
                    <span></span><span></span><span></span>
                </div>
            </div>
        </div>
    `;
    
    chatContainer.appendChild(div);
    scrollToBottom();
    return div;
}

// Remove loading message
function removeLoadingMessage() {
    const loading = chatContainer.querySelector('.loading-msg');
    if (loading) loading.remove();
}

// Send message
async function sendMessage() {
    const text = messageInput.value.trim();
    if (!text || state.isLoading) return;
    
    state.isLoading = true;
    sendBtn.disabled = true;
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    addUserMessage(text);
    const loadingDiv = addLoadingMessage();
    
    try {
        const history = state.messages.slice(-10).map(m => ({
            role: m.role,
            content: m.content
        }));
        
        const response = await fetch(`${state.apiUrl}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                history: history.slice(0, -1)
            })
        });
        
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        removeLoadingMessage();
        addAssistantMessage(data.response, data.is_emergency);
        
    } catch (err) {
        console.error(err);
        removeLoadingMessage();
        addAssistantMessage('⚠️ Bir hata oluştu. Backend sunucusuna bağlanılamıyor.\n\nLütfen sunucunun çalıştığından emin olun ve tekrar deneyin.', false);
    } finally {
        state.isLoading = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}
