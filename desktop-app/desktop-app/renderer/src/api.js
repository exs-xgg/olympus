/**
 * API client for the FastAPI backend.
 */

const API_BASE = 'http://localhost:8000/api';

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const config = {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Tasks
  createTask: (title, description) =>
    request('/tasks', {
      method: 'POST',
      body: JSON.stringify({ title, description }),
    }),

  listTasks: (status) =>
    request(`/tasks${status ? `?status=${status}` : ''}`),

  getTask: (taskId) =>
    request(`/tasks/${taskId}`),

  resumeTask: (taskId, humanInput) =>
    request(`/tasks/${taskId}/resume`, {
      method: 'POST',
      body: JSON.stringify({ human_input: humanInput }),
    }),

  rejectTask: (taskId, reason) =>
    request(`/tasks/${taskId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ reason }),
    }),

  getTaskLogs: (taskId) =>
    request(`/tasks/${taskId}/logs`),

  // Agents
  getAgentsStatus: () =>
    request('/agents/status'),
  listAgents: () =>
    request('/agents'),
  createAgent: (payload) =>
    request('/agents', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  chatWithAgent: (payload) =>
    request('/agents/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getAgentChatMessages: (threadId) =>
    request(`/agents/chat/${encodeURIComponent(threadId)}/messages`),

  // MCP Integrations
  listMcpServers: () => request('/mcp/servers'),
  createMcpServer: (payload) =>
    request('/mcp/servers', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  // Audit
  listInterventionAudit: () => request('/audit/interventions'),
};
