/**
 * Tutoring Agent POC - Frontend Application
 *
 * Handles WebSocket communication and UI interactions.
 */

class TutorApp {
    constructor() {
        this.ws = null;
        this.sessionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;

        // DOM Elements
        this.elements = {
            topicList: document.getElementById('topic-list'),
            topicName: document.getElementById('topic-name'),
            chatMessages: document.getElementById('chat-messages'),
            chatForm: document.getElementById('chat-form'),
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-button'),
            typingIndicator: document.getElementById('typing-indicator'),
            chatInputContainer: document.getElementById('chat-input-container'),
            progressSection: document.getElementById('progress-section'),
            masterySection: document.getElementById('mastery-section'),
            progressFill: document.getElementById('progress-fill'),
            progressText: document.getElementById('progress-text'),
            currentStep: document.getElementById('current-step'),
            currentConcept: document.getElementById('current-concept'),
            masteryList: document.getElementById('mastery-list'),
            // Modal elements
            viewStateBtn: document.getElementById('view-state-btn'),
            agentLogsLink: document.getElementById('agent-logs-link'),
            stateModal: document.getElementById('state-modal'),
            modalOverlay: document.getElementById('modal-overlay'),
            modalClose: document.getElementById('modal-close'),
            modalBody: document.getElementById('modal-body'),
        };

        this.init();
    }

    async init() {
        // Load available topics
        await this.loadTopics();

        // Setup event listeners
        this.setupEventListeners();
    }

    async loadTopics() {
        try {
            const response = await fetch('/api/topics');
            const topics = await response.json();

            if (topics.length === 0) {
                this.elements.topicList.innerHTML = '<p class="loading">No topics available</p>';
                return;
            }

            this.elements.topicList.innerHTML = topics.map(topic => `
                <div class="topic-item" data-topic-id="${topic.topic_id}">
                    <span class="topic-name">${topic.topic_name}</span>
                    <span class="topic-meta">${topic.subject} - Grade ${topic.grade_level}</span>
                </div>
            `).join('');

            // Add click handlers
            this.elements.topicList.querySelectorAll('.topic-item').forEach(item => {
                item.addEventListener('click', () => this.selectTopic(item.dataset.topicId));
            });

        } catch (error) {
            console.error('Failed to load topics:', error);
            this.elements.topicList.innerHTML = '<p class="loading">Failed to load topics</p>';
        }
    }

    async selectTopic(topicId) {
        try {
            // Close existing connection
            if (this.ws) {
                this.ws.close();
            }

            // Create session
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    topic_id: topicId,
                    student_context: { grade: 5, board: 'CBSE' }
                })
            });

            if (!response.ok) {
                throw new Error('Failed to create session');
            }

            const session = await response.json();
            this.sessionId = session.session_id;

            // Update UI
            this.elements.topicName.textContent = session.topic_name;

            // Mark topic as active
            this.elements.topicList.querySelectorAll('.topic-item').forEach(item => {
                item.classList.toggle('active', item.dataset.topicId === topicId);
            });

            // Show chat elements
            this.elements.chatInputContainer.style.display = 'block';
            this.elements.progressSection.style.display = 'block';
            this.elements.masterySection.style.display = 'block';
            this.elements.viewStateBtn.style.display = 'flex'; // Show view state button

            // Show agent logs link and update URL
            this.elements.agentLogsLink.style.display = 'flex';
            this.elements.agentLogsLink.href = `/agent-logs?session=${this.sessionId}`;

            // Clear messages
            this.elements.chatMessages.innerHTML = '';

            // Connect WebSocket
            this.connectWebSocket();

        } catch (error) {
            console.error('Failed to select topic:', error);
            this.showMessage('error', 'Failed to start session. Please try again.');
        }
    }

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/${this.sessionId}`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.reconnectAttempts = 0;
            this.enableInput();
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            this.handleServerMessage(message);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.disableInput();

            // Attempt reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                setTimeout(() => this.connectWebSocket(), 2000 * this.reconnectAttempts);
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    handleServerMessage(message) {
        switch (message.type) {
            case 'assistant':
                this.hideTyping();
                if (message.payload.message) {
                    this.showMessage('teacher', message.payload.message);
                }
                break;

            case 'state_update':
                if (message.payload.state) {
                    this.updateState(message.payload.state);
                }
                break;

            case 'error':
                this.hideTyping();
                this.showMessage('error', message.payload.error || 'An error occurred');
                break;

            case 'typing':
                this.showTyping();
                break;
        }
    }

    showMessage(type, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}`;
        messageDiv.textContent = content;

        this.elements.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }

    updateState(state) {
        // Update progress
        this.elements.progressFill.style.width = `${state.progress_percentage}%`;
        this.elements.progressText.textContent = `${Math.round(state.progress_percentage)}%`;
        this.elements.currentStep.textContent = `${state.current_step} / ${state.total_steps}`;
        this.elements.currentConcept.textContent = state.current_concept || '-';

        // Update mastery
        this.elements.masteryList.innerHTML = Object.entries(state.mastery_estimates || {})
            .map(([concept, score]) => {
                const percentage = Math.round(score * 100);
                const level = score < 0.4 ? 'low' : score < 0.7 ? 'medium' : 'high';
                return `
                    <div class="mastery-item">
                        <span class="concept-name">${concept.replace(/_/g, ' ')}</span>
                        <div class="mastery-bar">
                            <div class="mastery-fill ${level}" style="width: ${percentage}%"></div>
                        </div>
                    </div>
                `;
            }).join('');

        // Check if complete
        if (state.is_complete) {
            this.showMessage('teacher', 'Congratulations! You have completed this lesson.');
            this.disableInput();
        }
    }

    sendMessage(content) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.showMessage('error', 'Not connected. Please refresh the page.');
            return;
        }

        // Show user message
        this.showMessage('student', content);

        // Send to server
        this.ws.send(JSON.stringify({
            type: 'chat',
            payload: { message: content }
        }));

        // Clear input
        this.elements.messageInput.value = '';
    }

    showTyping() {
        this.elements.typingIndicator.style.display = 'flex';
        this.disableInput();
    }

    hideTyping() {
        this.elements.typingIndicator.style.display = 'none';
        this.enableInput();
    }

    enableInput() {
        this.elements.messageInput.disabled = false;
        this.elements.sendButton.disabled = false;
        this.elements.messageInput.focus();
    }

    disableInput() {
        this.elements.messageInput.disabled = true;
        this.elements.sendButton.disabled = true;
    }

    scrollToBottom() {
        this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
    }

    async openStateViewer() {
        if (!this.sessionId) {
            return;
        }

        // Show modal
        this.elements.stateModal.style.display = 'flex';
        this.elements.modalBody.innerHTML = '<div class="state-loading">Loading state...</div>';

        try {
            // Fetch detailed state
            const response = await fetch(`/api/sessions/${this.sessionId}/detailed`);
            if (!response.ok) {
                throw new Error('Failed to fetch state');
            }

            const state = await response.json();

            // Render state
            this.renderDetailedState(state);
        } catch (error) {
            console.error('Failed to load state:', error);
            this.elements.modalBody.innerHTML = '<div class="state-loading">Failed to load state. Please try again.</div>';
        }
    }

    closeStateViewer() {
        this.elements.stateModal.style.display = 'none';
    }

    renderDetailedState(state) {
        const html = `
            <!-- Session Info -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">📋</span>
                    Session Info
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Session ID</div>
                        <div class="state-field-value">${state.session_id}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Turn Count</div>
                        <div class="state-field-value">${state.turn_count}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Created</div>
                        <div class="state-field-value">${new Date(state.created_at).toLocaleString()}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Last Updated</div>
                        <div class="state-field-value">${new Date(state.updated_at).toLocaleString()}</div>
                    </div>
                </div>
            </div>

            <!-- Student Profile -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">👤</span>
                    Student Profile
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Grade</div>
                        <div class="state-field-value">${state.student_profile.grade}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Board</div>
                        <div class="state-field-value">${state.student_profile.board}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Language Level</div>
                        <div class="state-field-value">${state.student_profile.language_level}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Pace</div>
                        <div class="state-field-value">${state.student_profile.pace_preference}</div>
                    </div>
                </div>
                <div class="state-field" style="margin-top: 1rem;">
                    <div class="state-field-label">Preferred Examples</div>
                    <div class="state-field-value">${state.student_profile.preferred_examples.join(', ')}</div>
                </div>
            </div>

            ${state.topic ? `
            <!-- Topic Info -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">📚</span>
                    Topic: ${state.topic.topic_name}
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Subject</div>
                        <div class="state-field-value">${state.topic.subject}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Grade Level</div>
                        <div class="state-field-value">${state.topic.grade_level}</div>
                    </div>
                </div>
                <div class="state-field" style="margin-top: 1rem;">
                    <div class="state-field-label">Learning Objectives</div>
                    <ul class="state-list">
                        ${state.topic.learning_objectives.map(obj => `<li class="state-list-item">${obj}</li>`).join('')}
                    </ul>
                </div>
            </div>
            ` : ''}

            <!-- Progress -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">📊</span>
                    Progress (${Math.round(state.progress_percentage)}%)
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Current Step</div>
                        <div class="state-field-value">${state.current_step} of ${state.total_steps}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Last Concept</div>
                        <div class="state-field-value">${state.last_concept_taught || 'None yet'}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Overall Mastery</div>
                        <div class="state-field-value">${Math.round(state.overall_mastery * 100)}%</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Complete</div>
                        <div class="state-field-value">${state.is_complete ? 'Yes' : 'No'}</div>
                    </div>
                </div>
            </div>

            ${state.study_plan ? `
            <!-- Study Plan -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">🗺️</span>
                    Study Plan
                </div>
                <div class="study-plan-steps">
                    ${state.study_plan.steps.map(step => `
                        <div class="study-plan-step ${step.is_current ? 'current' : ''} ${step.is_completed ? 'completed' : ''}">
                            <div class="step-number">${step.step_id}</div>
                            <div class="step-info">
                                <div class="step-concept">${step.concept.replace(/_/g, ' ')}</div>
                                <div class="step-type">${step.type}</div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}

            <!-- Mastery Tracking -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">🎯</span>
                    Mastery Tracking
                </div>
                ${state.mastery_items.length > 0 ? `
                    <table class="mastery-table">
                        <thead>
                            <tr>
                                <th>Concept</th>
                                <th>Score</th>
                                <th>Level</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${state.mastery_items.map(item => `
                                <tr>
                                    <td>${item.concept.replace(/_/g, ' ')}</td>
                                    <td>${Math.round(item.score * 100)}%</td>
                                    <td><span class="mastery-badge ${item.level}">${item.level.replace(/_/g, ' ')}</span></td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                ` : '<div class="state-list-item empty">No mastery data yet</div>'}
            </div>

            <!-- Learning Insights -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">🧠</span>
                    Learning Insights
                </div>
                <div class="state-field" style="margin-bottom: 1rem;">
                    <div class="state-field-label">Progress Trend</div>
                    <div class="state-field-value">${state.session_summary.progress_trend}</div>
                </div>
                <div class="state-field" style="margin-bottom: 1rem;">
                    <div class="state-field-label">Misconceptions</div>
                    ${state.misconceptions.length > 0 ? `
                        <ul class="state-list">
                            ${state.misconceptions.map(m => `
                                <li class="state-list-item">
                                    <strong>${m.concept}:</strong> ${m.description}
                                    ${m.resolved ? ' ✓' : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<div class="state-list-item empty">No misconceptions detected</div>'}
                </div>
                <div class="state-field">
                    <div class="state-field-label">Weak Areas</div>
                    ${state.weak_areas.length > 0 ? `
                        <ul class="state-list">
                            ${state.weak_areas.map(area => `<li class="state-list-item">${area}</li>`).join('')}
                        </ul>
                    ` : '<div class="state-list-item empty">No weak areas identified</div>'}
                </div>
            </div>

            <!-- Session Timeline -->
            <div class="state-section" style="background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);">
                <div class="state-section-title" style="color: #0284c7;">
                    <span class="state-section-icon">📖</span>
                    Session Timeline
                </div>
                <div class="state-field" style="margin-bottom: 0.5rem;">
                    <div class="state-field-label">Progress Trend</div>
                    <div class="state-field-value" style="text-transform: capitalize; font-weight: 500;">
                        ${state.session_summary.progress_trend}
                    </div>
                </div>
                ${state.session_summary.turn_timeline.length > 0 ? `
                    <div class="state-field-label" style="margin-top: 1rem; margin-bottom: 0.5rem;">Turn History</div>
                    <ul class="state-list" style="max-height: 400px; overflow-y: auto;">
                        ${state.session_summary.turn_timeline.map(entry => `
                            <li class="state-list-item" style="font-size: 0.875rem; line-height: 1.6;">
                                ${entry}
                            </li>
                        `).join('')}
                    </ul>
                ` : '<div class="state-list-item empty">Session just started - timeline will appear as you interact</div>'}
            </div>

            <!-- Session Summary -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">💭</span>
                    Session Details
                </div>
                <div class="state-field" style="margin-bottom: 1rem;">
                    <div class="state-field-label">Concepts Taught</div>
                    ${state.session_summary.concepts_taught.length > 0 ? `
                        <div class="state-field-value">${state.session_summary.concepts_taught.join(', ')}</div>
                    ` : '<div class="state-list-item empty">No concepts taught yet</div>'}
                </div>
                <div class="state-field" style="margin-bottom: 1rem;">
                    <div class="state-field-label">Examples Used</div>
                    ${state.session_summary.examples_used.length > 0 ? `
                        <ul class="state-list">
                            ${state.session_summary.examples_used.map(ex => `<li class="state-list-item">${ex}</li>`).join('')}
                        </ul>
                    ` : '<div class="state-list-item empty">No examples used yet</div>'}
                </div>
                <div class="state-field">
                    <div class="state-field-label">Stuck Points & What Helped</div>
                    ${state.session_summary.stuck_points.length > 0 ? `
                        <ul class="state-list">
                            ${state.session_summary.stuck_points.map((point, i) => `
                                <li class="state-list-item">
                                    ⚠ ${point}
                                    ${state.session_summary.what_helped[i] ? `<br>✓ ${state.session_summary.what_helped[i]}` : ''}
                                </li>
                            `).join('')}
                        </ul>
                    ` : '<div class="state-list-item empty">No stuck points recorded</div>'}
                </div>
            </div>

            <!-- Behavioral -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">🎭</span>
                    Behavioral Tracking
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Off-Topic Count</div>
                        <div class="state-field-value">${state.behavioral.off_topic_count}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Warning Count</div>
                        <div class="state-field-value">${state.behavioral.warning_count}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Safety Flags</div>
                        <div class="state-field-value">${state.behavioral.safety_flags.length}</div>
                    </div>
                </div>
            </div>

            ${state.last_question ? `
            <!-- Current Question -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">❓</span>
                    Current Question
                </div>
                <div class="state-field" style="margin-bottom: 1rem;">
                    <div class="state-field-label">Question</div>
                    <div class="state-field-value">${state.last_question.question_text}</div>
                </div>
                <div class="state-grid">
                    <div class="state-field">
                        <div class="state-field-label">Concept</div>
                        <div class="state-field-value">${state.last_question.concept}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Hints Available</div>
                        <div class="state-field-value">${state.last_question.hints_available}</div>
                    </div>
                    <div class="state-field">
                        <div class="state-field-label">Hints Used</div>
                        <div class="state-field-value">${state.last_question.hints_used}</div>
                    </div>
                </div>
            </div>
            ` : ''}

            <!-- Conversation History -->
            <div class="state-section">
                <div class="state-section-title">
                    <span class="state-section-icon">💬</span>
                    Conversation History (Recent)
                </div>
                ${state.conversation_history.length > 0 ? `
                    <div class="conversation-messages">
                        ${state.conversation_history.map(msg => `
                            <div class="conversation-msg">
                                <div class="conversation-msg-header">
                                    <span class="conversation-msg-role ${msg.role}">${msg.role}</span>
                                    <span class="conversation-msg-time">${new Date(msg.timestamp).toLocaleTimeString()}</span>
                                </div>
                                <div class="conversation-msg-content">${msg.content}</div>
                            </div>
                        `).join('')}
                    </div>
                ` : '<div class="state-list-item empty">No conversation history yet</div>'}
            </div>
        `;

        this.elements.modalBody.innerHTML = html;
    }

    setupEventListeners() {
        // Form submission
        this.elements.chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const content = this.elements.messageInput.value.trim();
            if (content) {
                this.sendMessage(content);
            }
        });

        // Enter key handling
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                const content = this.elements.messageInput.value.trim();
                if (content) {
                    this.sendMessage(content);
                }
            }
        });

        // View State button
        this.elements.viewStateBtn.addEventListener('click', () => {
            this.openStateViewer();
        });

        // Modal close buttons
        this.elements.modalClose.addEventListener('click', () => {
            this.closeStateViewer();
        });

        this.elements.modalOverlay.addEventListener('click', () => {
            this.closeStateViewer();
        });

        // Close modal on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.elements.stateModal.style.display === 'flex') {
                this.closeStateViewer();
            }
        });
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.tutorApp = new TutorApp();
});
