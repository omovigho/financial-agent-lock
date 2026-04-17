import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

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
  login: (email: string, password: string) =>
    api.post('/api/auth/login', { email, password }),
  register: (email: string, password: string) =>
    api.post('/api/auth/register', { email, password }),
  me: () => api.get('/api/auth/me'),
}

export const tokenVaultAPI = {
  requirements: () => api.get('/api/token-vault/requirements'),
  exchange: (
    subjectToken: string,
    connection?: string,
    requiredScopes?: string[],
    loginHint?: string
  ) =>
    api.post('/api/token-vault/exchange', {
      subject_token: subjectToken,
      connection,
      required_scopes: requiredScopes,
      login_hint: loginHint,
    }),
}

export const agentAPI = {
  execute: (query: string, system: string, action: string, context?: Record<string, any>, simple?: boolean) =>
    api.post('/api/agent/execute', { query, system, action, context }, { params: { simple } }),
  listTools: () => api.get('/api/agent/tools'),
  listTokens: () => api.get('/api/agent/tokens'),
  requestToken: (system: string, scope: string, ttl_seconds?: number) =>
    api.post('/api/agent/token-request', { system, scope, ttl_seconds }),
}

export const policyAPI = {
  listPolicies: (system?: string) =>
    api.get('/api/policy/list', { params: { system } }),
  checkAction: (action: string, system: string, context?: Record<string, any>) =>
    api.get('/api/policy/check', { params: { action, system, context } }),
  dashboard: () => api.get('/api/policy/dashboard'),
  demo: () => api.get('/api/policy/demo'),
}

export const approvalAPI = {
  listPending: () => api.get('/api/approval/queue'),
  get: (id: number) => api.get(`/api/approval/${id}`),
  approve: (id: number, reason?: string) =>
    api.post(`/api/approval/${id}/approve`, { decision: 'approve', reason }),
  reject: (id: number, reason?: string) =>
    api.post(`/api/approval/${id}/reject`, { decision: 'reject', reason }),
  listAll: (status?: string) => api.get('/api/approval/queue', { params: { status_filter: status } }),
}

export const auditAPI = {
  listLogs: (userId?: number, system?: string, limit?: number) =>
    api.get('/api/audit/logs', { params: { user_id: userId, system, limit } }),
}

export const sessionAPI = {
  create: (context?: Record<string, any>, corpus_name?: string) =>
    api.post('/api/session/create', { context, corpus_name }),
  get: (sessionId: string) =>
    api.get(`/api/session/${sessionId}`),
  list: () =>
    api.get('/api/session/user/list'),
  update: (sessionId: string, data: Record<string, any>) =>
    api.put(`/api/session/${sessionId}`, data),
  updateContext: (sessionId: string, context: Record<string, any>) =>
    api.post(`/api/session/${sessionId}/context`, context),
  addToHistory: (sessionId: string, interaction: Record<string, any>) =>
    api.post(`/api/session/${sessionId}/history`, interaction),
  delete: (sessionId: string) =>
    api.delete(`/api/session/${sessionId}`),
}

export const knowledgeBaseAPI = {
  uploadDocument: (formData: FormData) =>
    api.post('/api/knowledge-base/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }),
  listDocuments: (statusFilter?: string) =>
    api.get('/api/knowledge-base/documents', { params: { status_filter: statusFilter } }),
  getDocument: (docId: string) =>
    api.get(`/api/knowledge-base/documents/${docId}`),
  deleteDocument: (
    docId: number | string,
    payload?: { doc_id?: string; filename?: string; reason?: string }
  ) =>
    api.delete(`/api/knowledge-base/documents/${docId}`, { data: { confirm: true, ...payload } }),
  getStats: () =>
    api.get('/api/knowledge-base/stats'),
  syncFromCorpus: () =>
    api.post('/api/knowledge-base/sync'),
}

export const supportAPI = {
  bootstrap: (ticketId?: number) =>
    api.get('/api/support/chat/bootstrap', { params: { ticket_id: ticketId } }),
  listConversations: () =>
    api.get('/api/support/chat/admin/conversations'),
  sendMessage: (ticketId: number, payload: { content: string; is_internal?: boolean }) =>
    api.post(`/api/support/chat/tickets/${ticketId}/message`, payload),
  updateMode: (ticketId: number, payload: { mode: 'agent' | 'human'; note?: string }) =>
    api.post(`/api/support/chat/tickets/${ticketId}/takeover`, payload),
  decideApproval: (
    ticketId: number,
    approvalId: number,
    payload: { decision: 'approve' | 'reject'; reason?: string }
  ) => api.post(`/api/support/chat/tickets/${ticketId}/approvals/${approvalId}`, payload),
}

