/**
 * Evaluation Dashboard Viewer
 *
 * Loads evaluation runs from the API and renders them in a
 * sidebar + tabbed detail layout.
 */
class EvaluationViewer {
    constructor() {
        this.runs = [];
        this.activeRunId = null;
        this.activeTab = 'conversation';
        this._pollTimer = null;

        this.sidebar = document.getElementById('run-list');
        this.runCount = document.getElementById('run-count');
        this.emptyState = document.getElementById('empty-state');
        this.detailContent = document.getElementById('detail-content');
        this.statusBar = document.getElementById('eval-status-bar');
        this.statusText = document.getElementById('eval-status-text');
        this.statusDetail = document.getElementById('eval-status-detail');
        this.runBtn = document.getElementById('run-eval-btn');

        this._bindTabs();
        this._bindRunButton();
        this.loadRuns();
        this._checkExistingRun();
    }

    // ───────── Data Loading ─────────

    async loadRuns() {
        try {
            const res = await fetch('/api/evaluation/runs');
            this.runs = await res.json();
            this._renderSidebar();
        } catch (err) {
            this.sidebar.innerHTML = `<p class="loading">Failed to load runs</p>`;
        }
    }

    async loadRunDetail(runId) {
        try {
            const res = await fetch(`/api/evaluation/runs/${runId}`);
            return await res.json();
        } catch (err) {
            return null;
        }
    }

    // ───────── Sidebar ─────────

    _renderSidebar() {
        if (this.runs.length === 0) {
            this.sidebar.innerHTML = '<p class="loading">No evaluation runs found</p>';
            this.runCount.textContent = '';
            return;
        }

        this.runCount.textContent = `${this.runs.length}`;

        this.sidebar.innerHTML = this.runs.map(run => {
            const date = this._formatDate(run.timestamp);
            const topic = this._formatTopic(run.topic_id);
            const scoreClass = this._scoreClass(run.avg_score);
            const scoreText = run.avg_score != null ? `${run.avg_score.toFixed(1)}` : '?';

            return `
                <div class="run-item" data-run-id="${run.run_id}">
                    <div class="run-item-header">
                        <span class="run-date">${date}</span>
                        <span class="run-score-badge ${scoreClass}">${scoreText}/10</span>
                    </div>
                    <div class="run-topic">${topic}</div>
                    <div class="run-meta">${run.message_count} messages &middot; <span class="run-id-copy" data-run-id="${run.run_id}" title="Click to copy">${run.run_id}</span></div>
                </div>
            `;
        }).join('');

        // Bind click events
        this.sidebar.querySelectorAll('.run-item').forEach(el => {
            el.addEventListener('click', () => this._selectRun(el.dataset.runId));
        });

        // Bind copy-on-click for run IDs
        this.sidebar.querySelectorAll('.run-id-copy').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(el.dataset.runId).then(() => {
                    const original = el.textContent;
                    el.textContent = 'Copied!';
                    el.classList.add('copied');
                    setTimeout(() => {
                        el.textContent = original;
                        el.classList.remove('copied');
                    }, 1200);
                });
            });
        });
    }

    async _selectRun(runId) {
        if (this.activeRunId === runId) return;
        this.activeRunId = runId;

        // Update sidebar active state
        this.sidebar.querySelectorAll('.run-item').forEach(el => {
            el.classList.toggle('active', el.dataset.runId === runId);
        });

        // Show loading
        this.emptyState.style.display = 'none';
        this.detailContent.style.display = 'flex';
        this._setTabContent('conversation', '<p class="loading">Loading...</p>');
        this._setTabContent('review', '');
        this._setTabContent('issues', '');

        const data = await this.loadRunDetail(runId);
        if (!data) {
            this._setTabContent('conversation', '<p class="loading">Failed to load run data</p>');
            return;
        }

        this._renderConversation(data);
        this._renderReview(data);
        this._renderIssues(data);
    }

    // ───────── Tabs ─────────

    _bindTabs() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const name = tab.dataset.tab;
                this.activeTab = name;

                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
                document.getElementById(`tab-${name}`).classList.add('active');
            });
        });
    }

    _setTabContent(name, html) {
        document.getElementById(`tab-${name}`).innerHTML = html;
    }

    // ───────── Conversation Tab ─────────

    _renderConversation(data) {
        const messages = data.messages || [];
        const topic = this._formatTopic(data.config?.topic_id);

        let html = `
            <div class="conv-summary">
                <span><strong>Topic:</strong> ${topic}</span>
                <span><strong>Messages:</strong> ${messages.length}</span>
            </div>
            <div class="conv-messages">
        `;

        let lastTurn = -1;
        for (const msg of messages) {
            const turn = msg.turn ?? '?';
            if (turn !== lastTurn) {
                html += `<div class="conv-turn-divider">Turn ${turn}</div>`;
                lastTurn = turn;
            }

            const role = msg.role === 'tutor' ? 'tutor' : 'student';
            const label = role === 'tutor' ? 'Tutor' : 'Student';
            html += `
                <div class="conv-bubble ${role}">
                    <div class="conv-bubble-label">${label}</div>
                    ${this._escapeHtml(msg.content)}
                </div>
            `;
        }

        html += '</div>';
        this._setTabContent('conversation', html);
    }

    // ───────── Review Tab ─────────

    _renderReview(data) {
        const evaluation = data.evaluation;
        if (!evaluation) {
            this._setTabContent('review', '<p class="no-issues">No evaluation data available</p>');
            return;
        }

        const scores = evaluation.scores || {};
        const analysis = evaluation.dimension_analysis || {};
        const summary = evaluation.summary || '';
        const avg = evaluation.avg_score;

        const avgClass = this._scoreClass(avg);

        let html = '';

        // Summary
        if (summary) {
            html += `
                <div class="review-summary">
                    <div class="review-summary-header">Summary</div>
                    ${this._escapeHtml(summary)}
                </div>
            `;
        }

        // Average score
        html += `
            <div class="review-avg">
                <span class="review-avg-number ${avgClass}">${avg != null ? avg.toFixed(1) : '?'}</span>
                <span class="review-avg-label">/ 10 average</span>
            </div>
        `;

        // Score bars
        html += '<div class="score-bars">';
        for (const [dim, score] of Object.entries(scores)) {
            const pct = (score / 10) * 100;
            const cls = this._scoreClass(score);
            const displayName = dim.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
            const analysisText = analysis[dim] || '';

            html += `
                <div class="score-row">
                    <div class="score-row-header">
                        <span class="score-dim-name">${displayName}</span>
                        <span class="score-value ${cls}">${score}/10</span>
                    </div>
                    <div class="score-bar-track">
                        <div class="score-bar-fill ${cls}" style="width: ${pct}%"></div>
                    </div>
                    ${analysisText ? `<div class="score-analysis">${this._escapeHtml(analysisText)}</div>` : ''}
                </div>
            `;
        }
        html += '</div>';

        this._setTabContent('review', html);
    }

    // ───────── Issues Tab ─────────

    _renderIssues(data) {
        const evaluation = data.evaluation;
        if (!evaluation) {
            this._setTabContent('issues', '<p class="no-issues">No evaluation data available</p>');
            return;
        }

        const problems = evaluation.problems || [];

        if (problems.length === 0) {
            this._setTabContent('issues', '<p class="no-issues">No problems identified</p>');
            return;
        }

        // Summary stats
        const critical = problems.filter(p => p.severity === 'critical').length;
        const major = problems.filter(p => p.severity === 'major').length;
        const minor = problems.filter(p => p.severity === 'minor').length;

        let html = `
            <div class="issues-summary">
                <div class="issues-stat"><strong>${problems.length}</strong> issues total</div>
                ${critical ? `<div class="issues-stat"><strong>${critical}</strong> critical</div>` : ''}
                ${major ? `<div class="issues-stat"><strong>${major}</strong> major</div>` : ''}
                ${minor ? `<div class="issues-stat"><strong>${minor}</strong> minor</div>` : ''}
            </div>
            <div class="issue-cards">
        `;

        for (const prob of problems) {
            const severity = prob.severity || 'unknown';
            const rootCause = (prob.root_cause || 'other').replace(/_/g, ' ');
            const turns = (prob.turns || []).map(t => `Turn ${t}`).join(', ');

            html += `
                <div class="issue-card severity-${severity}">
                    <div class="issue-card-header">
                        <span class="issue-title">${this._escapeHtml(prob.title || 'Untitled')}</span>
                        <div class="issue-badges">
                            <span class="severity-badge ${severity}">${severity}</span>
                            <span class="root-cause-tag">${rootCause}</span>
                        </div>
                    </div>
                    ${turns ? `<div class="issue-turns">${turns}</div>` : ''}
                    <div class="issue-description">${this._escapeHtml(prob.description || '')}</div>
                    ${prob.quote ? `<div class="issue-quote">${this._escapeHtml(prob.quote)}</div>` : ''}
                </div>
            `;
        }

        html += '</div>';
        this._setTabContent('issues', html);
    }

    // ───────── Run Trigger + Status Polling ─────────

    _bindRunButton() {
        this.runBtn.addEventListener('click', () => this._startEvaluation());
    }

    async _startEvaluation() {
        this.runBtn.disabled = true;
        try {
            const res = await fetch('/api/evaluation/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (res.status === 409) {
                // Already running, just show status
                this._showStatusBar();
                this._startPolling();
                return;
            }
            if (!res.ok) {
                const data = await res.json();
                alert('Failed to start evaluation: ' + (data.detail || res.statusText));
                this.runBtn.disabled = false;
                return;
            }
            this._showStatusBar();
            this._startPolling();
        } catch (err) {
            alert('Failed to start evaluation: ' + err.message);
            this.runBtn.disabled = false;
        }
    }

    _showStatusBar() {
        this.statusBar.style.display = 'block';
        this.statusBar.className = 'eval-status-bar';
        this.statusText.textContent = 'Starting...';
        this.statusDetail.textContent = '';
    }

    _startPolling() {
        if (this._pollTimer) clearInterval(this._pollTimer);
        this._pollStatus();
        this._pollTimer = setInterval(() => this._pollStatus(), 2000);
    }

    _stopPolling() {
        if (this._pollTimer) {
            clearInterval(this._pollTimer);
            this._pollTimer = null;
        }
    }

    async _pollStatus() {
        try {
            const res = await fetch('/api/evaluation/status');
            const state = await res.json();
            this._updateStatusBar(state);
        } catch (err) {
            // ignore transient errors
        }
    }

    _updateStatusBar(state) {
        const STATUS_LABELS = {
            idle: 'Idle',
            loading_persona: 'Loading persona...',
            running_session: 'Running session',
            evaluating: 'Evaluating conversation...',
            generating_reports: 'Generating reports...',
            complete: 'Complete',
            failed: 'Failed',
        };

        const label = STATUS_LABELS[state.status] || state.status;
        this.statusText.textContent = label;

        if (state.status === 'running_session' && state.turn > 0) {
            this.statusDetail.textContent = `Turn ${state.turn} / ${state.max_turns}`;
        } else if (state.detail && state.status !== 'complete' && state.status !== 'failed') {
            this.statusDetail.textContent = state.detail;
        } else {
            this.statusDetail.textContent = '';
        }

        // Terminal states
        if (state.status === 'complete') {
            this.statusBar.className = 'eval-status-bar status-complete';
            this.statusDetail.textContent = state.run_id || '';
            this.runBtn.disabled = false;
            this._stopPolling();
            // Reload sidebar and auto-select the new run
            this.loadRuns().then(() => {
                if (state.run_id) {
                    this._selectRun(state.run_id);
                }
            });
            // Hide status bar after a few seconds
            setTimeout(() => {
                this.statusBar.style.display = 'none';
            }, 5000);
        } else if (state.status === 'failed') {
            this.statusBar.className = 'eval-status-bar status-failed';
            this.statusDetail.textContent = state.error || 'Unknown error';
            this.runBtn.disabled = false;
            this._stopPolling();
            setTimeout(() => {
                this.statusBar.style.display = 'none';
            }, 8000);
        } else if (state.status === 'idle') {
            this.statusBar.style.display = 'none';
            this.runBtn.disabled = false;
            this._stopPolling();
        }
    }

    async _checkExistingRun() {
        try {
            const res = await fetch('/api/evaluation/status');
            const state = await res.json();
            if (state.status !== 'idle' && state.status !== 'complete' && state.status !== 'failed') {
                this._showStatusBar();
                this._updateStatusBar(state);
                this._startPolling();
                this.runBtn.disabled = true;
            }
        } catch (err) {
            // ignore
        }
    }

    // ───────── Helpers ─────────

    _scoreClass(score) {
        if (score == null) return '';
        if (score < 4) return 'score-low';
        if (score < 7) return 'score-mid';
        return 'score-high';
    }

    _formatDate(isoStr) {
        if (!isoStr) return 'Unknown';
        const d = new Date(isoStr);
        return d.toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    }

    _formatTopic(topicId) {
        if (!topicId) return 'Unknown';
        return topicId.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    }

    _escapeHtml(text) {
        const el = document.createElement('div');
        el.textContent = text;
        return el.innerHTML;
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    new EvaluationViewer();
});
