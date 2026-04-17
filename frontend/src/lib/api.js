import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const api = axios.create({
  baseURL: API_URL,
})

// Add token to headers if it exists
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export const authAPI = {
  login: (email, password) =>
    api.post('/api/auth/login', { email, password }),
  register: (email, password) =>
    api.post('/api/auth/register', { email, password }),
  me: () => api.get('/api/auth/me'),
  listUsers: () => api.get('/api/auth/users'),
  updateUserRole: (userId, role) =>
    api.put(`/api/auth/users/${userId}/role`, { user_id: userId, role }),
}

export const agentAPI = {
  execute: (query, system, action, context = {}, simple = false) =>
    api.post('/api/agent/execute', { query, system, action, context }, { params: { simple } }),
  listTools: () => api.get('/api/agent/tools'),
  listTokens: () => api.get('/api/agent/tokens'),
  requestToken: (system, scope, ttl_seconds) =>
    api.post('/api/agent/token-request', { system, scope, ttl_seconds }),
}

export const financialAPI = {
  getMySummary: (year) =>
    api.get('/api/financial/my/summary', { params: { year } }),
  getMyTransactions: (year, limit = 25) =>
    api.get('/api/financial/my/transactions', { params: { year, limit } }),
}

export const erpAPI = {
  getMySummary: (year) =>
    api.get('/api/erp/my/summary', { params: { year } }),
  getMyPurchaseOrders: (year, limit = 25, status) =>
    api.get('/api/erp/my/purchase-orders', { params: { year, limit, status } }),
}

export const policyAPI = {
  listPolicies: (system) =>
    api.get('/api/policy/list', { params: { system } }),
  checkAction: (action, system, context) =>
    api.get('/api/policy/check', { params: { action, system, context } }),
  dashboard: () => api.get('/api/policy/dashboard'),
  demo: () => api.get('/api/policy/demo'),
}

export const approvalAPI = {
  listPending: () => api.get('/api/approval/queue'),
  get: (id) => api.get(`/api/approval/${id}`),
  approve: (id, reason) =>
    api.post(`/api/approval/${id}/approve`, { decision: 'approve', reason }),
  reject: (id, reason) =>
    api.post(`/api/approval/${id}/reject`, { decision: 'reject', reason }),
  listAll: (status) => api.get('/api/approval/queue', { params: { status_filter: status } }),
}

export const auditAPI = {
  listLogs: (userId, system, limit) =>
    api.get('/api/audit/logs', { params: { user_id: userId, system, limit } }),
}

export const sessionAPI = {
  create: (context, corpus_name) =>
    api.post('/api/session/create', { context, corpus_name }),
  get: (sessionId) =>
    api.get(`/api/session/${sessionId}`),
  list: () =>
    api.get('/api/session/user/list'),
  update: (sessionId, data) =>
    api.put(`/api/session/${sessionId}`, data),
  updateContext: (sessionId, context) =>
    api.post(`/api/session/${sessionId}/context`, context),
  addToHistory: (sessionId, interaction) =>
    api.post(`/api/session/${sessionId}/history`, interaction),
  delete: (sessionId) =>
    api.delete(`/api/session/${sessionId}`),
}

export const knowledgeBaseAPI = {
  uploadDocument: (formData) =>
    api.post('/api/knowledge-base/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  listDocuments: (statusFilter) =>
    api.get('/api/knowledge-base/documents', { params: { status_filter: statusFilter } }),
  getDocument: (docId) =>
    api.get(`/api/knowledge-base/documents/${docId}`),
  deleteDocument: (docId, payload = {}) =>
    api.delete(`/api/knowledge-base/documents/${docId}`, { data: { confirm: true, ...payload } }),
  getStats: () =>
    api.get('/api/knowledge-base/stats'),
}

export const supportAPI = {
  bootstrap: (ticketId) =>
    api.get('/api/support/chat/bootstrap', { params: { ticket_id: ticketId } }),
  listConversations: () =>
    api.get('/api/support/chat/admin/conversations'),
  sendMessage: (ticketId, payload) =>
    api.post(`/api/support/chat/tickets/${ticketId}/message`, payload),
  updateMode: (ticketId, payload) =>
    api.post(`/api/support/chat/tickets/${ticketId}/takeover`, payload),
  decideApproval: (ticketId, approvalId, payload) =>
    api.post(`/api/support/chat/tickets/${ticketId}/approvals/${approvalId}`, payload),
}
