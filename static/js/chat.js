// Chat functionality
let isLoading = false;

function addMessage(content, isUser = false, videoUrl = null, videoTimestamp = null) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
    
    const messageContent = document.createElement('div');
    messageContent.className = 'message-content';
    messageContent.textContent = content;
    
    messageDiv.appendChild(messageContent);
    
    // Add video player if video URL is provided
    if (videoUrl && !isUser) {
        const videoContainer = document.createElement('div');
        videoContainer.className = 'video-container';
        
        const videoElement = document.createElement('video');
        videoElement.src = videoUrl;
        videoElement.controls = true;
        videoElement.className = 'video-clip';
        videoElement.preload = 'metadata';
        
        // If timestamp is provided, seek to that position when video loads
        if (videoTimestamp !== null && videoTimestamp > 0) {
            videoElement.addEventListener('loadedmetadata', () => {
                videoElement.currentTime = videoTimestamp;
            });
        }
        
        const videoLabel = document.createElement('div');
        videoLabel.className = 'video-label';
        const timestampText = videoTimestamp ? ` (starts at ${formatTime(videoTimestamp)})` : '';
        videoLabel.textContent = `🎬 Video teaching from Henry Shukman${timestampText}`;
        
        videoContainer.appendChild(videoLabel);
        videoContainer.appendChild(videoElement);
        messageDiv.appendChild(videoContainer);
    }
    
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatTime(seconds) {
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
}

function showLoading(show) {
    const loading = document.getElementById('loading');
    const sendButton = document.getElementById('sendButton');
    const questionInput = document.getElementById('questionInput');
    
    loading.style.display = show ? 'flex' : 'none';
    sendButton.disabled = show;
    questionInput.disabled = show;
    isLoading = show;
}

async function sendMessage() {
    if (isLoading) return;
    
    const questionInput = document.getElementById('questionInput');
    const question = questionInput.value.trim();
    
    if (!question) {
        alert('Please enter a question');
        return;
    }
    
    // Add user message to chat
    addMessage(question, true);
    
    // Clear input
    questionInput.value = '';
    
    // Show loading
    showLoading(true);
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ question: question })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            addMessage(data.response, false, data.video_url, data.video_timestamp);
        } else {
            addMessage(`Error: ${data.error || 'Something went wrong'}`);
        }
    } catch (error) {
        addMessage(`Error: Unable to connect to server. ${error.message}`);
    } finally {
        showLoading(false);
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    const questionInput = document.getElementById('questionInput');
    const sendButton = document.getElementById('sendButton');
    
    // Send message on Enter key
    questionInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Focus on input when page loads
    questionInput.focus();
    
    // Check if the server is healthy
    fetch('/health')
        .then(response => response.json())
        .then(data => {
            if (!data.qa_system_initialized) {
                addMessage('The teaching archive is being prepared. Please wait a moment...');
            }
        })
        .catch(error => {
            addMessage('The Way is temporarily unavailable. Please try again in a moment.');
        });
});