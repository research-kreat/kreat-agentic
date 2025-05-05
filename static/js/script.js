// Core configuration
const apiUrl = "http://localhost:5000";
let socket = null;

/**
 * Log a message to the console with timestamp
 */
function logToConsole(message, type = "info") {
    const consoleLog = document.getElementById("console-log");
    if (!consoleLog) return;

    const timestamp = new Date().toLocaleTimeString();
    const logDiv = document.createElement("div");
    logDiv.className = `log-message ${type}`;
    logDiv.innerHTML = `<span class="log-timestamp">${timestamp}</span> ${message}`;

    consoleLog.appendChild(logDiv);
    consoleLog.scrollTop = consoleLog.scrollHeight;
}

/**
 * Show a toast notification
 */
function showToast(message) {
    const toast = document.createElement("div");
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add("show"), 10);
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => document.body.removeChild(toast), 300);
    }, 3000);
}

/**
 * Navigation helper
 */
function navigateTo(page) {
    window.location.href = page;
}

/**
 * Connect to Socket.IO server
 */
function connectSocket() {
    try {
        socket = io.connect(apiUrl);
        
        socket.on("connect", () => {
            logToConsole("Connected to server", "system");
        });
        
        socket.on("disconnect", () => {
            logToConsole("Disconnected from server", "warning");
        });
        
        // Listen for chat message responses
        socket.on("chat_response", (data) => {
            if (typeof receiveMessage === "function") {
                receiveMessage(data);
            }
        });
        
        // Listen for typing indicators
        socket.on("typing_indicator", (data) => {
            if (typeof showTypingIndicator === "function" && currentSessionId) {
                if (data.session_id === currentSessionId) {
                    showTypingIndicator(data.is_typing);
                }
            }
        });
        
        // Listen for session updates
        socket.on("session_update", (data) => {
            if (typeof updateSessionInfo === "function" && currentSessionId) {
                if (data.session_id === currentSessionId) {
                    updateSessionInfo(data);
                }
            }
        });
        
        // Listen for new sessions
        socket.on("new_session_created", (data) => {
            if (typeof addSessionToList === "function") {
                addSessionToList(data, true);
            }
        });
        
    } catch (error) {
        logToConsole(`Error initializing socket: ${error}`, "error");
    }
}

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    connectSocket();
});