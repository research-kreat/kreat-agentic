let socket = null;
let currentSessionId = null;
let messageHistory = [];
let isTyping = false;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

// DOM elements that will be accessed frequently
let chatInput;
let chatMessages;
let sendButton;
let sessionIdSpan;
let sessionCreated;
let messageCount;
let sessionsList;

// Initialize on page load if this is the idea chat page
document.addEventListener("DOMContentLoaded", () => {
    // Get DOM elements
    chatInput = document.getElementById("chat-input");
    chatMessages = document.getElementById("chat-messages");
    sendButton = document.getElementById("send-button");
    sessionIdSpan = document.getElementById("session-id");
    sessionCreated = document.getElementById("session-created");
    messageCount = document.getElementById("message-count");
    sessionsList = document.getElementById("sessions-list");

    // Setup event listeners
    setupEventListeners();
    
    // Initialize Socket.IO
    initializeSocket();
    
    // Create or restore session
    initializeSession();
    
    // Auto-resize textarea
    setupTextareaAutoResize();
    
    // Load previous sessions
    loadPreviousSessions();
    
    logToConsole("Chat interface initialized", "system");
});

function setupEventListeners() {
    // Send message on button click
    if (sendButton) {
        sendButton.addEventListener("click", sendMessage);
    }
    
    // Send message on Enter key (without Shift key for newlines)
    if (chatInput) {
        chatInput.addEventListener("keydown", function(event) {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendMessage();
            }
        });
    }
    
    // Clear chat button
    const clearChatBtn = document.getElementById("clear-chat-btn");
    if (clearChatBtn) {
        clearChatBtn.addEventListener("click", clearChat);
    }
    
    // Export chat button
    const exportChatBtn = document.getElementById("export-chat-btn");
    if (exportChatBtn) {
        exportChatBtn.addEventListener("click", exportChat);
    }
    
    // New session button
    const newSessionBtn = document.getElementById("new-session-btn");
    if (newSessionBtn) {
        newSessionBtn.addEventListener("click", createNewSession);
    }
}

function initializeSocket() {
    // Connect to Socket.IO server
    try {
        socket = io.connect(window.location.origin);
        
        socket.on("connect", () => {
            logToConsole("Connected to server", "system");
            reconnectAttempts = 0;
        });
        
        socket.on("disconnect", () => {
            logToConsole("Disconnected from server", "warning");
        });
        
        socket.on("error", (error) => {
            logToConsole(`Socket error: ${error}`, "error");
            attemptReconnect();
        });
        
        // Listen for chat message responses
        socket.on("chat_response", (data) => {
            receiveMessage(data);
        });
        
        // Listen for typing indicators
        socket.on("typing_indicator", (data) => {
            if (data.session_id === currentSessionId) {
                showTypingIndicator(data.is_typing);
            }
        });
        
        // Listen for session updates
        socket.on("session_update", (data) => {
            if (data.session_id === currentSessionId) {
                updateSessionInfo(data);
            }
        });
        
        // Listen for new sessions
        socket.on("new_session_created", (data) => {
            addSessionToList(data, true);
        });
        
        // Listen for session list updates
        socket.on("sessions_list", (data) => {
            updateSessionsList(data);
        });
        
    } catch (error) {
        logToConsole(`Error initializing socket: ${error}`, "error");
    }
}

function attemptReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        logToConsole(`Attempting to reconnect (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`, "warning");
        
        setTimeout(() => {
            initializeSocket();
        }, 2000 * reconnectAttempts); // Exponential backoff
    } else {
        logToConsole("Maximum reconnection attempts reached. Please refresh the page.", "error");
    }
}

function initializeSession() {
    // Check URL for session ID
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get("session");
    
    if (sessionId) {
        // Restore existing session
        currentSessionId = sessionId;
        loadSession(sessionId);
    } else {
        // Create new session
        createNewSession();
    }
}

function loadSession(sessionId) {
    fetch(`/api/sessions/${sessionId}`)
        .then(response => {
            if (!response.ok) {
                throw new Error("Session not found");
            }
            return response.json();
        })
        .then(data => {
            // Update session info
            currentSessionId = sessionId;
            updateSessionInfo(data.session);
            
            // Load messages
            messageHistory = data.messages || [];
            renderMessages(messageHistory);
            
            // Update URL without reloading page
            updateURL(sessionId);
            
            logToConsole(`Loaded session: ${sessionId}`, "system");
        })
        .catch(error => {
            logToConsole(`Error loading session: ${error}`, "error");
            // Create new session if loading fails
            createNewSession();
        });
}

function createNewSession() {
    fetch("/api/sessions/new", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            type: "idea",
            name: "New Idea Session"
        })
    })
    .then(response => response.json())
    .then(data => {
        currentSessionId = data.session_id;
        
        // Clear chat and history
        clearChat(false);
        
        // Update session info
        updateSessionInfo(data);
        
        // Update URL without reloading page
        updateURL(currentSessionId);
        
        logToConsole(`Created new session: ${currentSessionId}`, "system");
        
        // Add welcome message
        const welcomeMsg = {
            role: "system",
            content: "Welcome to a new Idea Development session. How can I help you today?",
            timestamp: new Date().toISOString()
        };
        
        // Add to message history and render
        messageHistory.push(welcomeMsg);
        addMessageToUI(welcomeMsg);
    })
    .catch(error => {
        logToConsole(`Error creating new session: ${error}`, "error");
    });
}

function loadPreviousSessions() {
    fetch("/api/sessions?type=idea&limit=10")
        .then(response => response.json())
        .then(data => {
            updateSessionsList(data.sessions || []);
        })
        .catch(error => {
            logToConsole(`Error loading sessions: ${error}`, "error");
            sessionsList.innerHTML = `<li>Error loading sessions</li>`;
        });
}

function updateSessionsList(sessions) {
    if (!sessionsList) return;
    
    if (!sessions || sessions.length === 0) {
        sessionsList.innerHTML = `<li>No previous sessions found</li>`;
        return;
    }
    
    // Clear current list
    sessionsList.innerHTML = "";
    
    // Add each session to the list
    sessions.forEach(session => {
        addSessionToList(session);
    });
}

function addSessionToList(session, isNew = false) {
    if (!sessionsList) return;
    
    // Check if session already exists in list
    const existingItem = document.getElementById(`session-${session.session_id}`);
    if (existingItem) {
        // Update existing item
        existingItem.querySelector(".session-title").textContent = session.name || `Session ${session.session_id.substring(0, 8)}`;
        
        // Highlight if it's a new update
        if (isNew) {
            existingItem.classList.add("updated");
            setTimeout(() => {
                existingItem.classList.remove("updated");
            }, 2000);
        }
        return;
    }
    
    // Create new list item
    const li = document.createElement("li");
    li.id = `session-${session.session_id}`;
    li.className = "session-item";
    if (session.session_id === currentSessionId) {
        li.classList.add("active");
    }
    
    // Format date
    const date = new Date(session.created_at);
    const formattedDate = date.toLocaleDateString() + " " + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    li.innerHTML = `
        <div class="session-title">${session.name || `Session ${session.session_id.substring(0, 8)}`}</div>
        <div class="session-date">${formattedDate}</div>
    `;
    
    // Add click handler to load session
    li.addEventListener("click", () => {
        loadSession(session.session_id);
    });
    
    // Add to list (new sessions at the top)
    if (isNew) {
        li.classList.add("new");
        sessionsList.insertBefore(li, sessionsList.firstChild);
        setTimeout(() => {
            li.classList.remove("new");
        }, 2000);
    } else {
        sessionsList.appendChild(li);
    }
}

function updateSessionInfo(session) {
    if (!session) return;
    
    // Update session ID display
    if (sessionIdSpan) {
        sessionIdSpan.textContent = `Session: ${session.session_id.substring(0, 8)}...`;
    }
    
    // Update created date
    if (sessionCreated) {
        const date = new Date(session.created_at);
        sessionCreated.textContent = date.toLocaleString();
    }
    
    // Update message count
    updateMessageCount();
    
    // Update active session in list
    const sessionItems = document.querySelectorAll(".session-item");
    sessionItems.forEach(item => {
        if (item.id === `session-${session.session_id}`) {
            item.classList.add("active");
        } else {
            item.classList.remove("active");
        }
    });
}

function updateMessageCount() {
    if (messageCount) {
        messageCount.textContent = messageHistory.length;
    }
}

function updateURL(sessionId) {
    if (!sessionId) return;
    
    // Update URL without refreshing page
    const url = new URL(window.location.href);
    url.searchParams.set("session", sessionId);
    window.history.pushState({ sessionId }, "", url);
}

function sendMessage() {
    // Get message text
    const message = chatInput.value.trim();
    
    // Don't send empty messages
    if (!message) return;
    
    // Disable input and button while sending
    chatInput.disabled = true;
    sendButton.disabled = true;
    
    // Create message object
    const msgObj = {
        role: "user",
        content: message,
        timestamp: new Date().toISOString(),
        session_id: currentSessionId
    };
    
    // Add to UI immediately
    addMessageToUI(msgObj);
    
    // Clear input
    chatInput.value = "";
    
    // Add to history
    messageHistory.push(msgObj);
    
    // Update message count
    updateMessageCount();
    
    logToConsole(`Sending message: "${message.substring(0, 30)}${message.length > 30 ? '...' : ''}"`, "info");
    
    // Show typing indicator
    showTypingIndicator(true);
    
    // Send to server
    fetch("/api/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            message: message,
            session_id: currentSessionId
        })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Failed to send message");
        }
        return response.json();
    })
    .catch(error => {
        logToConsole(`Error sending message: ${error}`, "error");
        
        // Hide typing indicator
        showTypingIndicator(false);
        
        // Show error message
        const errorMsg = {
            role: "system",
            content: `Error: ${error.message}. Please try again.`,
            timestamp: new Date().toISOString(),
            error: true
        };
        
        addMessageToUI(errorMsg);
        messageHistory.push(errorMsg);
    })
    .finally(() => {
        // Re-enable input and button
        chatInput.disabled = false;
        sendButton.disabled = false;
        chatInput.focus();
    });
}

function receiveMessage(data) {
    // Hide typing indicator
    showTypingIndicator(false);
    
    if (!data) return;
    
    // Create message object
    const msgObj = {
        role: "assistant",
        content: data.response || data.content || "No response received",
        timestamp: data.timestamp || new Date().toISOString()
    };
    
    // Add to UI
    addMessageToUI(msgObj);
    
    // Add to history
    messageHistory.push(msgObj);
    
    // Update message count
    updateMessageCount();
    
    logToConsole("Received response from assistant", "info");
    
    // Process any follow-up actions
    if (data.actions && data.actions.length > 0) {
        processActions(data.actions);
    }
}

function addMessageToUI(message) {
    if (!chatMessages || !message) return;
    
    // Create message element
    const msgElement = document.createElement("div");
    msgElement.className = `message ${message.role}`;
    if (message.error) {
        msgElement.classList.add("error");
    }
    
    // Format timestamp
    const timestamp = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    
    // Create message content with avatar for user and assistant
    if (message.role === "system") {
        msgElement.innerHTML = `
            <div class="message-content">
                <p>${formatMessageContent(message.content)}</p>
            </div>
        `;
    } else {
        msgElement.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${message.role === 'user' ? 'fa-user' : 'fa-robot'}"></i>
            </div>
            <div class="message-content">
                <p>${formatMessageContent(message.content)}</p>
                <div class="message-time">${timestamp}</div>
            </div>
        `;
    }
    
    // Add to chat
    chatMessages.appendChild(msgElement);
    
    // Scroll to bottom
    scrollToBottom();
}

function formatMessageContent(content) {
    if (!content) return "";
    
    // Convert URLs to links
    content = content.replace(
        /(https?:\/\/[^\s]+)/g, 
        '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>'
    );
    
    // Convert markdown-style code blocks to HTML
    content = content.replace(
        /```([^`]+)```/g,
        '<pre><code>$1</code></pre>'
    );
    
    // Convert markdown-style inline code to HTML
    content = content.replace(
        /`([^`]+)`/g,
        '<code>$1</code>'
    );
    
    // Handle line breaks
    content = content.replace(/\n/g, '<br>');
    
    return content;
}

function renderMessages(messages) {
    if (!chatMessages || !messages) return;
    
    // Clear chat
    chatMessages.innerHTML = "";
    
    // Add each message to UI
    messages.forEach(msg => {
        addMessageToUI(msg);
    });
    
    // Scroll to bottom
    scrollToBottom();
}

function scrollToBottom() {
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

function showTypingIndicator(show) {
    // Don't update if state hasn't changed
    if (isTyping === show) return;
    
    isTyping = show;
    
    // Remove existing indicator if any
    const existingIndicator = chatMessages.querySelector(".typing-indicator-container");
    if (existingIndicator) {
        chatMessages.removeChild(existingIndicator);
    }
    
    if (show) {
        // Create typing indicator
        const indicatorContainer = document.createElement("div");
        indicatorContainer.className = "message assistant typing-indicator-container";
        
        indicatorContainer.innerHTML = `
            <div class="message-avatar">
                <i class="fas fa-robot"></i>
            </div>
            <div class="message-content">
                <div class="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;
        
        // Add to chat
        chatMessages.appendChild(indicatorContainer);
        
        // Scroll to bottom
        scrollToBottom();
    }
}

function setupTextareaAutoResize() {
    if (!chatInput) return;
    
    // Auto-resize function
    const resize = () => {
        chatInput.style.height = "auto";
        chatInput.style.height = Math.min(chatInput.scrollHeight, 120) + "px";
    };
    
    // Add event listeners
    chatInput.addEventListener("input", resize);
    chatInput.addEventListener("focus", resize);
    
    // Initial resize
    resize();
}

function clearChat(askConfirmation = true) {
    if (askConfirmation && messageHistory.length > 1) {
        if (!confirm("Are you sure you want to clear this chat? This cannot be undone.")) {
            return;
        }
    }
    
    // Clear UI
    if (chatMessages) {
        chatMessages.innerHTML = "";
    }
    
    // Clear history (keep only system welcome message)
    const systemMessages = messageHistory.filter(msg => msg.role === "system");
    messageHistory = systemMessages.length > 0 
        ? [systemMessages[0]] 
        : [{
            role: "system",
            content: "Chat has been cleared. How can I help you today?",
            timestamp: new Date().toISOString()
        }];
    
    // Show system message in UI
    renderMessages(messageHistory);
    
    // Update message count
    updateMessageCount();
    
    logToConsole("Chat cleared", "system");
    
    // Notify server of clearing if we have a session
    if (currentSessionId) {
        fetch(`/api/sessions/${currentSessionId}/clear`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error("Failed to clear chat on server");
            }
            return response.json();
        })
        .catch(error => {
            logToConsole(`Error clearing chat on server: ${error}`, "error");
        });
    }
}

function exportChat() {
    if (!messageHistory || messageHistory.length === 0) {
        alert("No messages to export");
        return;
    }
    
    // Create export object
    const exportData = {
        session_id: currentSessionId,
        messages: messageHistory,
        exported_at: new Date().toISOString(),
        type: "idea_development"
    };
    
    // Convert to JSON string
    const jsonStr = JSON.stringify(exportData, null, 2);
    
    // Create download link
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement("a");
    a.href = url;
    a.download = `kraft-chat-${currentSessionId.substring(0, 8)}-${new Date().toISOString().slice(0, 10)}.json`;
    
    // Trigger download
    document.body.appendChild(a);
    a.click();
    
    // Clean up
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 100);
    
    logToConsole("Chat exported to JSON", "info");
}

function processActions(actions) {
    if (!actions || actions.length === 0) return;
    
    actions.forEach(action => {
        switch (action.type) {
            case "rename_session":
                if (action.name) {
                    renameSession(action.name);
                }
                break;
                
            case "suggest_followup":
                if (action.suggestions && action.suggestions.length > 0) {
                    showSuggestions(action.suggestions);
                }
                break;
                
            case "redirect":
                if (action.url) {
                    showRedirectPrompt(action.url, action.message);
                }
                break;
                
            default:
                logToConsole(`Unknown action type: ${action.type}`, "warning");
        }
    });
}

function renameSession(name) {
    if (!currentSessionId || !name) return;
    
    fetch(`/api/sessions/${currentSessionId}/rename`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({ name })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error("Failed to rename session");
        }
        return response.json();
    })
    .then(data => {
        logToConsole(`Session renamed to: ${name}`, "info");
        
        // Update session in list
        const sessionItem = document.getElementById(`session-${currentSessionId}`);
        if (sessionItem) {
            const titleEl = sessionItem.querySelector(".session-title");
            if (titleEl) {
                titleEl.textContent = name;
            }
        }
    })
    .catch(error => {
        logToConsole(`Error renaming session: ${error}`, "error");
    });
}

function showSuggestions(suggestions) {
    if (!suggestions || suggestions.length === 0) return;
    
    // Create suggestions element
    const suggestionsEl = document.createElement("div");
    suggestionsEl.className = "message system suggestions";
    
    // Create content
    let content = `<div class="message-content"><p>Here are some suggested follow-up questions:</p><div class="suggestion-buttons">`;
    
    suggestions.forEach(suggestion => {
        content += `<button class="suggestion-button">${suggestion}</button>`;
    });
    
    content += `</div></div>`;
    suggestionsEl.innerHTML = content;
    
    // Add to chat
    chatMessages.appendChild(suggestionsEl);
    
    // Add click handlers
    const buttons = suggestionsEl.querySelectorAll(".suggestion-button");
    buttons.forEach(button => {
        button.addEventListener("click", () => {
            chatInput.value = button.textContent;
            chatInput.focus();
            
            // Remove suggestions after clicking
            chatMessages.removeChild(suggestionsEl);
        });
    });
    
    // Scroll to bottom
    scrollToBottom();
}

function showRedirectPrompt(url, message) {
    const msg = message || `Would you like to continue to ${url}?`;
    
    // Create redirect element
    const redirectEl = document.createElement("div");
    redirectEl.className = "message system redirect";
    
    redirectEl.innerHTML = `
        <div class="message-content">
            <p>${msg}</p>
            <div class="redirect-actions">
                <a href="${url}" target="_blank" class="redirect-button">Open Link</a>
                <button class="redirect-dismiss">Dismiss</button>
            </div>
        </div>
    `;
    
    // Add to chat
    chatMessages.appendChild(redirectEl);
    
    // Add dismiss handler
    const dismissBtn = redirectEl.querySelector(".redirect-dismiss");
    if (dismissBtn) {
        dismissBtn.addEventListener("click", () => {
            chatMessages.removeChild(redirectEl);
        });
    }
    
    // Scroll to bottom
    scrollToBottom();
}

// Handle page visibility changes to detect when user returns to the page
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && currentSessionId) {
        // Request any new messages that may have been sent while page was hidden
        fetch(`/api/sessions/${currentSessionId}/messages?after=${messageHistory.length}`)
            .then(response => response.json())
            .then(data => {
                if (data.messages && data.messages.length > 0) {
                    // Add new messages to chat
                    data.messages.forEach(msg => {
                        // Check if message is already in history
                        const exists = messageHistory.some(m => 
                            m.timestamp === msg.timestamp && 
                            m.content === msg.content && 
                            m.role === msg.role
                        );
                        
                        if (!exists) {
                            messageHistory.push(msg);
                            addMessageToUI(msg);
                        }
                    });
                    
                    // Update message count
                    updateMessageCount();
                }
            })
            .catch(error => {
                logToConsole(`Error checking for new messages: ${error}`, "error");
            });
    }
});

// Handle page reload/close to save session state
window.addEventListener("beforeunload", () => {
    if (currentSessionId) {
        // Use sendBeacon for reliable delivery even during page unload
        navigator.sendBeacon(
            `/api/sessions/${currentSessionId}/heartbeat`,
            JSON.stringify({ last_active: new Date().toISOString() })
        );
    }
});

// Additional helper utility to log to the console display
function logToConsole(message, type = "info") {
    const consoleLog = document.getElementById("console-log");
    if (!consoleLog) return;

    const timestamp = new Date().toLocaleTimeString();
    const logDiv = document.createElement("div");
    logDiv.className = `log-message ${type}`;
    logDiv.innerHTML = `<span class="log-timestamp">${timestamp}</span> ${message}`;

    consoleLog.appendChild(logDiv);
    consoleLog.scrollTop = consoleLog.scrollHeight;
    
    // Limit log size to prevent memory issues
    while (consoleLog.children.length > 100) {
        consoleLog.removeChild(consoleLog.children[0]);
    }
}