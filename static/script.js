document.addEventListener('DOMContentLoaded', () => {
    const chatBox = document.getElementById('chat-box');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const llmSelect = document.getElementById('llm-select');

    let chatHistory = []; // Stores messages as { role: 'user'/'assistant', content: '...' }

    // Optional: Add a default system prompt if desired by a model
    // chatHistory.push({ role: 'system', content: 'You are a helpful assistant.' });

    function addMessageToChatBox(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', role);
        
        // Basic Markdown-like rendering for newlines
        // For full Markdown, you'd need a library like Marked.js
        messageDiv.innerHTML = content.replace(/\n/g, '<br>'); 
        
        chatBox.appendChild(messageDiv);
        chatBox.scrollTop = chatBox.scrollHeight; // Auto-scroll to bottom
    }

    async function sendMessage() {
        const messageText = userInput.value.trim();
        if (!messageText) return;

        addMessageToChatBox('user', messageText);
        chatHistory.push({ role: 'user', content: messageText });
        userInput.value = ''; // Clear input field
        sendButton.disabled = true; // Disable send button while waiting

        // Add a thinking indicator
        const thinkingDiv = document.createElement('div');
        thinkingDiv.classList.add('message', 'assistant');
        thinkingDiv.textContent = 'Thinking...';
        chatBox.appendChild(thinkingDiv);
        chatBox.scrollTop = chatBox.scrollHeight;

        try {
            const selectedModel = llmSelect.value;
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    messages: chatHistory,
                    model: selectedModel
                }),
            });

            chatBox.removeChild(thinkingDiv); // Remove thinking indicator

            if (!response.ok) {
                const errorData = await response.json();
                addMessageToChatBox('assistant', `Error: ${errorData.detail || response.statusText}`);
                return;
            }

            const data = await response.json();
            addMessageToChatBox('assistant', data.content);
            chatHistory.push({ role: 'assistant', content: data.content });

        } catch (error) {
            chatBox.removeChild(thinkingDiv); // Remove thinking indicator
            console.error('Error sending message:', error);
            addMessageToChatBox('assistant', 'Sorry, something went wrong. Please try again.');
        } finally {
            sendButton.disabled = false; // Re-enable send button
            userInput.focus();
        }
    }

    sendButton.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (event) => {
        if (event.key === 'Enter') {
            sendMessage();
        }
    });
});