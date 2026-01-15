/**
 * Agent Logs Viewer
 *
 * Displays real-time agent execution logs for a tutoring session.
 */

class AgentLogsViewer {
    constructor() {
        this.sessionId = null;
        this.autoRefreshInterval = null;
        this.logs = [];

        this.elements = {
            sessionInput: document.getElementById('session-input'),
            loadBtn: document.getElementById('load-btn'),
            refreshBtn: document.getElementById('refresh-btn'),
            autoRefresh: document.getElementById('auto-refresh'),
            agentFilter: document.getElementById('agent-filter'),
            turnFilter: document.getElementById('turn-filter'),
            logsList: document.getElementById('logs-list'),
            logsCount: document.getElementById('logs-count'),
            lastUpdated: document.getElementById('last-updated'),
            detailModal: document.getElementById('detail-modal'),
            detailOverlay: document.getElementById('detail-overlay'),
            detailClose: document.getElementById('detail-close'),
            detailTitle: document.getElementById('detail-title'),
            detailBody: document.getElementById('detail-body'),
        };

        this.init();
    }

    init() {
        // Check URL params for session ID
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get('session');
        if (sessionId) {
            this.elements.sessionInput.value = sessionId;
            this.loadLogs(sessionId);
        }

        // Event listeners
        this.elements.loadBtn.addEventListener('click', () => this.handleLoad());
        this.elements.refreshBtn.addEventListener('click', () => this.handleRefresh());
        this.elements.autoRefresh.addEventListener('change', (e) => this.handleAutoRefreshToggle(e.target.checked));
        this.elements.agentFilter.addEventListener('change', () => this.filterLogs());
        this.elements.turnFilter.addEventListener('input', () => this.filterLogs());
        this.elements.sessionInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleLoad();
        });

        // Modal close
        this.elements.detailClose.addEventListener('click', () => this.closeDetailModal());
        this.elements.detailOverlay.addEventListener('click', () => this.closeDetailModal());

        // Start auto-refresh if enabled
        if (this.elements.autoRefresh.checked && sessionId) {
            this.startAutoRefresh();
        }
    }

    handleLoad() {
        const sessionId = this.elements.sessionInput.value.trim();
        if (!sessionId) {
            alert('Please enter a session ID');
            return;
        }

        // Update URL
        const url = new URL(window.location);
        url.searchParams.set('session', sessionId);
        window.history.pushState({}, '', url);

        this.loadLogs(sessionId);
    }

    handleRefresh() {
        if (this.sessionId) {
            this.loadLogs(this.sessionId);
        }
    }

    handleAutoRefreshToggle(enabled) {
        if (enabled && this.sessionId) {
            this.startAutoRefresh();
        } else {
            this.stopAutoRefresh();
        }
    }

    startAutoRefresh() {
        this.stopAutoRefresh(); // Clear any existing interval
        this.autoRefreshInterval = setInterval(() => {
            if (this.sessionId) {
                this.loadLogs(this.sessionId, false); // Silent refresh
            }
        }, 3000); // 3 seconds
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    async loadLogs(sessionId, showLoading = true) {
        this.sessionId = sessionId;

        if (showLoading) {
            this.elements.logsList.innerHTML = '<div class="loading-state"><p>Loading logs...</p></div>';
        }

        try {
            const response = await fetch(`/api/sessions/${sessionId}/agent-logs?limit=200`);

            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Session not found');
                } else if (response.status === 410) {
                    throw new Error('Session expired');
                } else {
                    throw new Error(`Failed to load logs: ${response.statusText}`);
                }
            }

            const data = await response.json();
            this.logs = data.logs;
            this.renderLogs();
            this.updateStats();
        } catch (error) {
            console.error('Error loading logs:', error);
            this.elements.logsList.innerHTML = `
                <div class="error-state">
                    <p>Error: ${error.message}</p>
                    <p>Please check the session ID and try again.</p>
                </div>
            `;
            this.stopAutoRefresh();
        }
    }

    filterLogs() {
        const agentFilter = this.elements.agentFilter.value;
        const turnFilter = this.elements.turnFilter.value.trim().toLowerCase();

        const filteredLogs = this.logs.filter(log => {
            const matchesAgent = !agentFilter || log.agent_name === agentFilter;
            const matchesTurn = !turnFilter || log.turn_id?.toLowerCase().includes(turnFilter);
            return matchesAgent && matchesTurn;
        });

        this.renderLogs(filteredLogs);
    }

    renderLogs(logsToRender = null) {
        const logs = logsToRender || this.logs;

        if (logs.length === 0) {
            this.elements.logsList.innerHTML = `
                <div class="empty-state">
                    <p>No logs found.</p>
                    <p>Logs will appear here as the tutor processes student messages.</p>
                </div>
            `;
            return;
        }

        // Group logs by turn
        const logsByTurn = this.groupLogsByTurn(logs);

        let html = '';
        for (const [turnId, turnLogs] of Object.entries(logsByTurn)) {
            html += this.renderTurn(turnId, turnLogs);
        }

        this.elements.logsList.innerHTML = html;

        // Add click handlers for expand buttons
        this.elements.logsList.querySelectorAll('.log-expand-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const logId = e.target.closest('.log-expand-btn').dataset.logId;
                const log = logs.find((l, idx) => idx === parseInt(logId));
                if (log) this.openDetailModal(log);
            });
        });
    }

    groupLogsByTurn(logs) {
        const groups = {};
        logs.forEach(log => {
            const turnId = log.turn_id || 'unknown';
            if (!groups[turnId]) {
                groups[turnId] = [];
            }
            groups[turnId].push(log);
        });
        return groups;
    }

    renderTurn(turnId, turnLogs) {
        const turnNumber = turnId.replace('turn_', '');

        let html = `
            <div class="turn-group">
                <div class="turn-header">
                    <h3>Turn ${turnNumber}</h3>
                    <span class="turn-logs-count">${turnLogs.length} events</span>
                </div>
                <div class="turn-logs">
        `;

        turnLogs.forEach((log, idx) => {
            html += this.renderLogEntry(log, idx);
        });

        html += `
                </div>
            </div>
        `;

        return html;
    }

    renderLogEntry(log, idx) {
        const agentClass = `agent-${log.agent_name}`;
        const eventClass = `event-${log.event_type}`;
        const timestamp = new Date(log.timestamp).toLocaleTimeString();

        // Prepare output preview
        let outputPreview = 'N/A';
        if (log.output) {
            const outputStr = JSON.stringify(log.output, null, 2);
            outputPreview = outputStr.length > 150
                ? outputStr.substring(0, 150) + '...'
                : outputStr;
        }

        // Reasoning preview
        let reasoningPreview = log.reasoning || 'N/A';
        if (reasoningPreview.length > 150) {
            reasoningPreview = reasoningPreview.substring(0, 150) + '...';
        }

        return `
            <div class="log-entry ${agentClass} ${eventClass}">
                <div class="log-header">
                    <div class="log-meta">
                        <span class="agent-badge">${log.agent_name}</span>
                        <span class="event-badge">${log.event_type}</span>
                        ${log.model ? `<span class="model-badge">${log.model}</span>` : ''}
                        <span class="timestamp">${timestamp}</span>
                        ${log.duration_ms ? `<span class="duration">${log.duration_ms}ms</span>` : ''}
                    </div>
                    <button class="log-expand-btn" data-log-id="${idx}" title="View full details">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <polyline points="9 18 15 12 9 6"></polyline>
                        </svg>
                    </button>
                </div>

                ${log.input_summary ? `
                    <div class="log-section">
                        <div class="section-label">Input:</div>
                        <div class="section-content input-content">${this.escapeHtml(log.input_summary)}</div>
                    </div>
                ` : ''}

                <div class="log-section">
                    <div class="section-label">Output:</div>
                    <div class="section-content output-content"><pre>${this.escapeHtml(outputPreview)}</pre></div>
                </div>

                ${log.reasoning ? `
                    <div class="log-section">
                        <div class="section-label">Reasoning:</div>
                        <div class="section-content reasoning-content">${this.escapeHtml(reasoningPreview)}</div>
                    </div>
                ` : ''}

                ${log.prompt ? `
                    <div class="log-section prompt-section">
                        <div class="prompt-toggle" onclick="window.logsViewer.togglePrompt(this)">
                            <span class="section-label">Prompt:</span>
                            <span class="toggle-icon">▶</span>
                            <span class="prompt-length">(${log.prompt.length.toLocaleString()} chars)</span>
                        </div>
                        <div class="prompt-content collapsed">
                            <pre>${this.escapeHtml(log.prompt)}</pre>
                        </div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    togglePrompt(toggleElement) {
        const promptContent = toggleElement.nextElementSibling;
        const toggleIcon = toggleElement.querySelector('.toggle-icon');

        if (promptContent.classList.contains('collapsed')) {
            promptContent.classList.remove('collapsed');
            toggleIcon.textContent = '▼';
        } else {
            promptContent.classList.add('collapsed');
            toggleIcon.textContent = '▶';
        }
    }

    openDetailModal(log) {
        const timestamp = new Date(log.timestamp).toLocaleString();

        this.elements.detailTitle.textContent = `${log.agent_name} - ${log.event_type}`;

        let html = `
            <div class="detail-section">
                <h3>Metadata</h3>
                <table class="detail-table">
                    <tr><td><strong>Timestamp:</strong></td><td>${timestamp}</td></tr>
                    <tr><td><strong>Agent:</strong></td><td>${log.agent_name}</td></tr>
                    <tr><td><strong>Event:</strong></td><td>${log.event_type}</td></tr>
                    ${log.model ? `<tr><td><strong>Model:</strong></td><td>${log.model}</td></tr>` : ''}
                    ${log.duration_ms ? `<tr><td><strong>Duration:</strong></td><td>${log.duration_ms}ms</td></tr>` : ''}
                    <tr><td><strong>Turn ID:</strong></td><td>${log.turn_id || 'N/A'}</td></tr>
                </table>
            </div>
        `;

        if (log.input_summary) {
            html += `
                <div class="detail-section">
                    <h3>Input Summary</h3>
                    <div class="detail-content">${this.escapeHtml(log.input_summary)}</div>
                </div>
            `;
        }

        if (log.prompt) {
            html += `
                <div class="detail-section">
                    <h3>Prompt</h3>
                    <pre class="detail-json">${this.escapeHtml(log.prompt)}</pre>
                </div>
            `;
        }

        if (log.output) {
            html += `
                <div class="detail-section">
                    <h3>Output</h3>
                    <pre class="detail-json">${JSON.stringify(log.output, null, 2)}</pre>
                </div>
            `;
        }

        if (log.reasoning) {
            html += `
                <div class="detail-section">
                    <h3>Reasoning</h3>
                    <div class="detail-content">${this.escapeHtml(log.reasoning)}</div>
                </div>
            `;
        }

        this.elements.detailBody.innerHTML = html;
        this.elements.detailModal.style.display = 'block';
    }

    closeDetailModal() {
        this.elements.detailModal.style.display = 'none';
    }

    updateStats() {
        const count = this.logs.length;
        const now = new Date().toLocaleTimeString();

        this.elements.logsCount.textContent = `${count} log${count !== 1 ? 's' : ''}`;
        this.elements.lastUpdated.textContent = `Updated: ${now}`;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.logsViewer = new AgentLogsViewer();
});
