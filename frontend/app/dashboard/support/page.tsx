'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { supportAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

type ChatMessage = {
  id: number
  sender_type: 'customer' | 'agent' | 'system'
  content: string
  created_at: string
  is_internal: boolean
  custom_metadata?: Record<string, any>
}

type ConversationSummary = {
  ticket_id: number
  customer_name: string
  customer_email: string
  status: string
  priority: string
  chat_mode: 'agent' | 'human'
  last_message: string
  last_message_at: string
}

type TicketPayload = {
  id: number
  ticket_number: string
  status: string
  priority: string
  chat_mode: 'agent' | 'human'
  customer: {
    id: number
    name: string
    email: string
  }
  compaction?: {
    compaction_interval: number
    overlap_size: number
    invocation_count: number
    last_compacted_at?: string
  }
}

export default function SupportPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [sending, setSending] = useState(false)
  const [switchingMode, setSwitchingMode] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [ticket, setTicket] = useState<TicketPayload | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [selectedTicketId, setSelectedTicketId] = useState<number | undefined>(undefined)

  const [draft, setDraft] = useState('')
  const [takeoverNote, setTakeoverNote] = useState('')

  const loadChat = useCallback(async (ticketId?: number, silent?: boolean) => {
    if (silent) {
      setRefreshing(true)
    } else {
      setLoading(true)
    }
    setError(null)

    try {
      const response = await supportAPI.bootstrap(ticketId)
      const data = response.data || {}

      setTicket(data.ticket || null)
      setMessages(data.messages || [])
      setConversations(data.conversations || [])
      if (data.ticket?.id) {
        setSelectedTicketId(data.ticket.id)
      }
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to load support chat.'
      setError(detail)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadChat(undefined, false)
  }, [loadChat])

  useEffect(() => {
    const interval = setInterval(() => {
      if (selectedTicketId) {
        loadChat(selectedTicketId, true)
      } else {
        loadChat(undefined, true)
      }
    }, 8000)

    return () => clearInterval(interval)
  }, [loadChat, selectedTicketId])

  const handleSend = async () => {
    if (!ticket || !draft.trim()) return

    setSending(true)
    setError(null)

    try {
      await supportAPI.sendMessage(ticket.id, { content: draft.trim() })
      setDraft('')
      await loadChat(ticket.id, true)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to send message.'
      setError(detail)
    } finally {
      setSending(false)
    }
  }

  const handleToggleMode = async () => {
    if (!ticket || !isAdmin) return

    setSwitchingMode(true)
    setError(null)

    const nextMode = ticket.chat_mode === 'agent' ? 'human' : 'agent'
    try {
      await supportAPI.updateMode(ticket.id, {
        mode: nextMode,
        note: takeoverNote.trim() || undefined,
      })
      setTakeoverNote('')
      await loadChat(ticket.id, true)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to switch chat mode.'
      setError(detail)
    } finally {
      setSwitchingMode(false)
    }
  }

  const handleApprovalDecision = async (approvalId: number, decision: 'approve' | 'reject') => {
    if (!ticket || !isAdmin) return

    setError(null)
    try {
      await supportAPI.decideApproval(ticket.id, approvalId, { decision })
      await loadChat(ticket.id, true)
    } catch (err: any) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to submit approval decision.'
      setError(detail)
    }
  }

  const sortedMessages = useMemo(() => {
    return [...messages].sort((a, b) => {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    })
  }, [messages])

  const composerPlaceholder = isAdmin
    ? 'Reply as support agent...'
    : ticket?.chat_mode === 'human'
      ? 'Support team is in human takeover mode. Share additional details...'
      : 'Describe your issue. The agent will validate your transactions first.'

  if (loading) {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="card p-8 text-center text-gray-600">Loading support workspace...</div>
      </div>
    )
  }

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-6">
      <div className="card p-6 bg-gradient-to-r from-blue-50 via-white to-emerald-50">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Customer Support Chat</h1>
            <p className="text-sm text-gray-600 mt-2">
              Transaction-first verification, document-grounded answers, admin approvals, and human takeover.
            </p>
          </div>
          <div className="text-sm text-gray-600">
            {ticket?.compaction ? (
              <span className="badge badge-info">
                Context Compaction: every {ticket.compaction.compaction_interval} turns, overlap {ticket.compaction.overlap_size}
              </span>
            ) : null}
            {refreshing ? <span className="ml-2 text-xs text-gray-500">Refreshing...</span> : null}
          </div>
        </div>
      </div>

      {error ? (
        <div className="card p-4 border-red-300 bg-red-50 text-red-700 text-sm">{error}</div>
      ) : null}

      <div className={`grid gap-6 ${isAdmin ? 'grid-cols-1 lg:grid-cols-12' : 'grid-cols-1'}`}>
        {isAdmin ? (
          <div className="lg:col-span-4 card p-4 space-y-3 max-h-[75vh] overflow-auto">
            <h2 className="text-lg font-semibold text-gray-900">All Customer Conversations</h2>
            {conversations.length === 0 ? (
              <p className="text-sm text-gray-500">No customer conversations yet.</p>
            ) : (
              conversations.map((conversation) => (
                <button
                  key={conversation.ticket_id}
                  onClick={() => {
                    setSelectedTicketId(conversation.ticket_id)
                    loadChat(conversation.ticket_id, false)
                  }}
                  className={`w-full text-left p-3 rounded-lg border transition-colors ${
                    selectedTicketId === conversation.ticket_id
                      ? 'border-blue-400 bg-blue-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-medium text-gray-900">{conversation.customer_name}</p>
                      <p className="text-xs text-gray-500">{conversation.customer_email}</p>
                    </div>
                    <span className={`badge ${conversation.chat_mode === 'human' ? 'badge-warning' : 'badge-info'}`}>
                      {conversation.chat_mode}
                    </span>
                  </div>
                  <p className="text-xs text-gray-600 mt-2 line-clamp-2">
                    {conversation.last_message || 'No messages yet'}
                  </p>
                </button>
              ))
            )}
          </div>
        ) : null}

        <div className={`${isAdmin ? 'lg:col-span-8' : ''} card p-0 overflow-hidden`}>
          {!ticket ? (
            <div className="p-8 text-center text-gray-500">Select a conversation to begin.</div>
          ) : (
            <>
              <div className="border-b border-gray-200 p-4 bg-white">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {ticket.customer.name} · {ticket.ticket_number}
                    </h2>
                    <p className="text-xs text-gray-500">
                      {ticket.customer.email} · Status: {ticket.status} · Priority: {ticket.priority}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`badge ${ticket.chat_mode === 'human' ? 'badge-warning' : 'badge-success'}`}>
                      Mode: {ticket.chat_mode.toUpperCase()}
                    </span>
                    {isAdmin ? (
                      <button
                        onClick={handleToggleMode}
                        disabled={switchingMode}
                        className="btn-outline text-sm"
                      >
                        {switchingMode
                          ? 'Switching...'
                          : ticket.chat_mode === 'agent'
                            ? 'Take Over (Human)'
                            : 'Return To Agent'}
                      </button>
                    ) : null}
                  </div>
                </div>

                {isAdmin ? (
                  <div className="mt-3 flex gap-2">
                    <input
                      value={takeoverNote}
                      onChange={(event) => setTakeoverNote(event.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                      placeholder="Optional note for takeover switch"
                    />
                  </div>
                ) : null}
              </div>

              <div className="h-[52vh] overflow-auto p-4 bg-gray-50 space-y-3">
                {sortedMessages.length === 0 ? (
                  <div className="text-center text-sm text-gray-500 mt-10">
                    Start the conversation. Messages are persisted and shared with support admins.
                  </div>
                ) : (
                  sortedMessages.map((message) => {
                    const approval = message.custom_metadata?.approval
                    const isCustomerMessage = message.sender_type === 'customer'
                    const isSystemMessage = message.sender_type === 'system'

                    return (
                      <div
                        key={message.id}
                        className={`flex ${
                          isSystemMessage ? 'justify-center' : isCustomerMessage ? 'justify-start' : 'justify-end'
                        }`}
                      >
                        <div
                          className={`max-w-[85%] rounded-xl p-3 border ${
                            isSystemMessage
                              ? 'bg-amber-50 border-amber-200 text-amber-900'
                              : isCustomerMessage
                                ? 'bg-white border-gray-200 text-gray-900'
                                : 'bg-blue-600 border-blue-600 text-white'
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                          <p className={`text-[11px] mt-2 ${isCustomerMessage ? 'text-gray-500' : isSystemMessage ? 'text-amber-800' : 'text-blue-100'}`}>
                            {new Date(message.created_at).toLocaleString()}
                          </p>

                          {message.custom_metadata?.knowledge_sources?.length ? (
                            <div className="mt-2 text-[11px] opacity-90">
                              Source: {message.custom_metadata.knowledge_sources.join(', ')}
                            </div>
                          ) : null}

                          {approval?.required ? (
                            <div className="mt-3 rounded-lg p-3 bg-white text-gray-800 border border-gray-200">
                              <p className="text-xs font-semibold">Approval Required</p>
                              <p className="text-xs mt-1">{approval.request_summary}</p>
                              <p className="text-xs mt-1 text-gray-500">Approval ID: {approval.approval_id}</p>
                              {isAdmin ? (
                                <div className="flex gap-2 mt-3">
                                  <button
                                    onClick={() => handleApprovalDecision(approval.approval_id, 'approve')}
                                    className="btn-secondary text-xs"
                                  >
                                    Approve
                                  </button>
                                  <button
                                    onClick={() => handleApprovalDecision(approval.approval_id, 'reject')}
                                    className="btn-danger text-xs"
                                  >
                                    Reject
                                  </button>
                                </div>
                              ) : (
                                <p className="text-xs mt-2 text-gray-500">Waiting for admin decision.</p>
                              )}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>

              <div className="border-t border-gray-200 p-4 bg-white">
                <div className="flex gap-3">
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={composerPlaceholder}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg min-h-[72px] focus:outline-none focus:ring-2 focus:ring-blue-400"
                    disabled={sending}
                  />
                  <button
                    onClick={handleSend}
                    disabled={sending || !draft.trim() || !ticket}
                    className="btn-primary self-end"
                  >
                    {sending ? 'Sending...' : 'Send'}
                  </button>
                </div>
              </div>
            </>
          )}
          </div>
        </div>
      </div>
    </div>
  )
}
