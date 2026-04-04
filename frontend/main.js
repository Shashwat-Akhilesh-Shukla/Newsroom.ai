// Global State
const state = {
    agents: {
        scout: 'idle',
        researcher: 'idle',
        skeptic: 'idle',
        writer: 'idle',
        editor: 'idle',
        publisher: 'idle'
    },
    latestOutputRun: null
};

// DOM Elements
const logOutput = document.getElementById('log-output');
const docPreview = document.getElementById('document-preview');
const mdContent = document.getElementById('markdown-content');
const btnClose = document.getElementById('btn-close-preview');
const btnDownloadDocx = document.getElementById('btn-download-docx');

// Utility: Update Agent UI
function updateAgentUI(agentName, status) {
    const el = document.getElementById(agentName);
    if (!el) return;
    
    // Remove old classes
    el.classList.remove('idle', 'running', 'completed', 'error');
    // Add new class
    el.classList.add(status);
}

// Utility: Append Log
function appendLog(text) {
    const isAtBottom = logOutput.scrollHeight - logOutput.scrollTop <= logOutput.clientHeight + 50;
    
    const span = document.createElement('span');
    span.textContent = text + '\n';
    logOutput.appendChild(span);
    
    if (isAtBottom) {
        logOutput.scrollTop = logOutput.scrollHeight;
    }
}

// Connection to Backend Websocket
function connectWebSocket() {
    // Assuming backend is running on 8000
    const wsUrl = `ws://127.0.0.1:8000/ws/events`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        appendLog('>>> Frontend connected to AI Newsroom Workflow server over WebSocket.');
    };

    ws.onmessage = (messageEvent) => {
        try {
            const data = JSON.parse(messageEvent.data);
            
            if (data.type === 'log') {
                appendLog(data.message.trim());
                
                // Hacky deduction of output run path from logs since event stream might not emit it explicitly
                const logMsg = data.message;
                const match = logMsg.match(/Artifacts stored in: .*run_([\d_]+)/);
                if (match) {
                    state.latestOutputRun = `run_${match[1]}`;
                    setTimeout(() => fetchResults(state.latestOutputRun), 1000);
                }
            } else {
                // Structured event format: {agent, event, message, data}
                const { agent, event, message } = data;
                
                if (agent && ['scout', 'researcher', 'skeptic', 'writer', 'editor', 'publisher'].includes(agent.toLowerCase())) {
                    const agentId = agent.toLowerCase();
                    if (event === 'started' || event === 'running') {
                        updateAgentUI(agentId, 'running');
                    } else if (event === 'completed') {
                        updateAgentUI(agentId, 'completed');
                    } else if (event === 'error') {
                        updateAgentUI(agentId, 'error');
                    }
                }
            }

        } catch (e) {
            // Not JSON, just raw text?
            appendLog(messageEvent.data);
        }
    };

    ws.onclose = () => {
        appendLog('>>> Disconnected. Trying to reconnect in 3s...');
        setTimeout(connectWebSocket, 3000);
    };
    
    ws.onerror = (err) => {
        appendLog('>>> WebSocket Error occurred.');
    };
}

// Fetch and render output results
async function fetchResults(runId) {
    appendLog(`>>> Fetching final artifacts for ${runId}...`);
    try {
        const urlMd = `http://127.0.0.1:8000/output/${runId}/article.md`;
        const res = await fetch(urlMd);
        if (res.ok) {
            const mdText = await res.text();
            mdContent.innerHTML = marked.parse(mdText);
            docPreview.classList.remove('hidden');
            
            // Set docx download link
            btnDownloadDocx.href = `http://127.0.0.1:8000/output/${runId}/article.docx`;
        } else {
            appendLog(`>>> Failed to fetch article.md. Status: ${res.status}`);
        }
    } catch (err) {
        appendLog(`>>> Error fetching results: ${err}`);
    }
}

// UI Triggers
btnClose.addEventListener('click', () => {
    docPreview.classList.add('hidden');
});

// Init
appendLog('>>> Booting interface...');
connectWebSocket();
