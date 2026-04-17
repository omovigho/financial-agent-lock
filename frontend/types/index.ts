export interface User {
  id: number
  email: string
  name: string
  auth0_id: string
  role: string
}

export interface Token {
  token_id: string
  scope: string
  system: string
  expires_at: string
  created_at: string
}

export interface Policy {
  id: number
  name: string
  action: string
  system: string
  rule: string
  description?: string
}

export interface Approval {
  id: number
  action: string
  system: string
  status: 'pending' | 'approved' | 'denied' | 'expired'
  created_at: string
  expires_at: string
  request_data: Record<string, any>
  approved_by?: string
  reason?: string
}

export interface Transaction {
  id: number
  date: string
  description: string
  amount: number
  category: string
}

export interface AuditLog {
  id: number
  user_id: number
  action: string
  system: string
  resource: string
  method: string
  status: 'success' | 'failure' | 'blocked'
  reason?: string
  created_at: string
}

export interface AgentResponse {
  status: 'success' | 'pending' | 'blocked' | 'failure'
  decision: string
  data?: Record<string, any>
  approval_id?: number
  token?: string
  requirements?: Record<string, any>
}

export interface Session {
  session_id: string
  user_id: number
  context: Record<string, any>
  conversation_history: Array<Record<string, any>>
  current_corpus: string
  is_active: boolean
  created_at: string
  last_activity_at: string
  expires_at: string
}

export interface KnowledgeBaseDocument {
  id: number
  doc_id: string
  filename: string
  file_extension: string
  file_size_bytes: number
  corpus_id: string
  status: 'active' | 'archived' | 'deleted'
  embedded_at?: string
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseStats {
  corpus_name: string
  total_documents: number
  active_documents: number
  total_size_bytes: number
  total_size_mb: number
}

export interface TimelineEvent {
  id: string
  timestamp: string
  type: 'agent_reasoning' | 'policy_check' | 'token_request' | 'execution'
  status: 'pending' | 'success' | 'failed'
  message: string
  details?: string
}

export interface InteractionStream {
  id: string
  user_email: string
  action: string
  system: string
  risk_level: 'low' | 'medium' | 'high'
  status: 'success' | 'blocked' | 'pending'
  timestamp: string
  metadata: Record<string, any>
}
