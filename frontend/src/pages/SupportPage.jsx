import { useCallback, useEffect, useMemo, useState } from 'react'
import { supportAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'

export default function SupportPage() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'

  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [sending, setSending] = useState(false)
  const [switchingMode, setSwitchingMode] = useState(false)
  const [error, setError] = useState(null)

  const [ticket, setTicket] = useState(null)
  const [messages, setMessages] = useState([])
  const [conversations, setConversations] = useState([])
  const [selectedTicketId, setSelectedTicketId] = useState(undefined)

  const [draft, setDraft] = useState('')
  const [takeoverNote, setTakeoverNote] = useState('')

  const loadChat = useCallback(async (ticketId, silent = false) => {
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
    } catch (err) {
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
    const timer = setInterval(() => {
      if (selectedTicketId) {
        loadChat(selectedTicketId, true)
      } else {
        loadChat(undefined, true)
      }
    }, 8000)

    return () => clearInterval(timer)
  }, [loadChat, selectedTicketId])

  const handleSend = async () => {
    if (!ticket || !draft.trim()) return

    setSending(true)
    setError(null)

    try {
      await supportAPI.sendMessage(ticket.id, { content: draft.trim() })
      setDraft('')
      await loadChat(ticket.id, true)
    } catch (err) {
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
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to switch mode.'
      setError(detail)
    } finally {
      setSwitchingMode(false)
    }
  }

  const handleApprovalDecision = async (approvalId, decision) => {
    if (!ticket || !isAdmin) return
    setError(null)

    try {
      await supportAPI.decideApproval(ticket.id, approvalId, { decision })
      await loadChat(ticket.id, true)
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to submit approval.'
      setError(detail)
    }
  }

  const sortedMessages = useMemo(() => {
    return [...messages].sort((a, b) => {
      return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    })
  }, [messages])

  const placeholder = isAdmin
    ? 'Reply as support team...'
    : ticket?.chat_mode === 'human'
      ? 'Human support has taken over. Share any extra details...'
      : 'Ask your support question. The agent validates transactions first.'

  if (loading) {
    return (
      <div className="p-8 max-w-7xl mx-auto">
        <div className="card p-8 text-center text-gray-600">Loading support workspace...</div>
      </div>
    )
  }

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      <section className="rounded-2xl border border-teal-100 bg-gradient-to-r from-emerald-50 via-cyan-50 to-sky-100 p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h1 className="text-3xl md:text-4xl font-black tracking-tight text-slate-900">Support Chat Workspace</h1>
            <p className="text-slate-700 mt-2 text-sm md:text-base">
              Persistent customer conversations with transaction-first verification, knowledge-backed answers, and human takeover.
            </p>
          </div>
          <div className="text-sm text-slate-700">
            {refreshing ? <span className="ml-2 text-xs">Refreshing...</span> : null}
          </div>
        </div>
      </section>

      {error ? (
        <div className="rounded-xl border border-rose-300 bg-rose-50 text-rose-700 px-4 py-3 text-sm">{error}</div>
      ) : null}

      <div className={`grid gap-6 ${isAdmin ? 'grid-cols-1 lg:grid-cols-12' : 'grid-cols-1'}`}>
        {isAdmin ? (
          <aside className="lg:col-span-4 rounded-2xl border border-slate-200 bg-white shadow-sm p-4 max-h-[74vh] overflow-auto">
            <h2 className="text-lg font-bold text-slate-900 mb-3">Customer List</h2>
            {conversations.length === 0 ? (
              <p className="text-sm text-slate-500">No conversations yet.</p>
            ) : (
              <div className="space-y-2">
                {conversations.map((item) => (
                  <button
                    key={item.ticket_id}
                    onClick={() => {
                      setSelectedTicketId(item.ticket_id)
                      loadChat(item.ticket_id, false)
                    }}
                    className={`w-full text-left rounded-xl border p-3 transition-all ${
                      selectedTicketId === item.ticket_id
                        ? 'border-cyan-400 bg-cyan-50'
                        : 'border-slate-200 hover:bg-slate-50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <p className="font-semibold text-slate-900">{item.customer_name}</p>
                        <p className="text-xs text-slate-500">{item.customer_email}</p>
                      </div>
                      <span className={`text-[10px] px-2 py-1 rounded-full ${item.chat_mode === 'human' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700'}`}>
                        {item.chat_mode}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-2 line-clamp-2">{item.last_message || 'No messages yet'}</p>
                  </button>
                ))}
              </div>
            )}
          </aside>
        ) : null}

        <section className={`${isAdmin ? 'lg:col-span-8' : ''} rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden`}>
          {!ticket ? (
            <div className="p-10 text-center text-slate-500">No active support ticket yet.</div>
          ) : (
            <>
              <header className="border-b border-slate-200 bg-white p-4">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-slate-900">
                      {ticket.customer?.name} • {ticket.ticket_number}
                    </h2>
                    <p className="text-xs text-slate-500">
                      {ticket.customer?.email} • {ticket.status} • {ticket.priority}
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded-full ${ticket.chat_mode === 'human' ? 'bg-amber-100 text-amber-800' : 'bg-emerald-100 text-emerald-700'}`}>
                      {ticket.chat_mode === 'human' ? 'Human takeover' : 'Agent active'}
                    </span>
                    {isAdmin ? (
                      <button onClick={handleToggleMode} disabled={switchingMode} className="btn-secondary text-sm">
                        {switchingMode
                          ? 'Switching...'
                          : ticket.chat_mode === 'agent'
                            ? 'Take Over'
                            : 'Return To Agent'}
                      </button>
                    ) : null}
                  </div>
                </div>

                {isAdmin ? (
                  <input
                    value={takeoverNote}
                    onChange={(event) => setTakeoverNote(event.target.value)}
                    placeholder="Optional note for mode switch"
                    className="mt-3 w-full input text-sm"
                  />
                ) : null}
              </header>

              <div className="h-[54vh] overflow-auto bg-slate-50 p-4 space-y-3">
                {sortedMessages.length === 0 ? (
                  <div className="text-center text-sm text-slate-500 mt-10">Start chatting with support.</div>
                ) : (
                  sortedMessages.map((message) => {
                    const isCustomer = message.sender_type === 'customer'
                    const isSystem = message.sender_type === 'system'
                    const isHumanAdminMessage = Boolean(isAdmin && message.custom_metadata?.source === 'human_support')
                    const isAgentMessage = Boolean(message.sender_type === 'agent' && !isHumanAdminMessage)
                    const approval = message.custom_metadata?.approval
                    const approvalStatus = (approval?.status || '').toLowerCase()
                    const isApprovalPending = approval?.required && (!approvalStatus || approvalStatus === 'pending')

                    return (
                      <div
                        key={message.id}
                        className={`flex ${isSystem ? 'justify-center' : isCustomer ? 'justify-start' : 'justify-end'}`}
                      >
                        <div
                          className={`max-w-[86%] rounded-2xl p-3 border shadow-sm ${
                            isSystem
                              ? 'bg-amber-50 border-amber-200 text-amber-900'
                              : isCustomer
                                ? 'bg-white border-slate-200 text-slate-900'
                                : isAdmin && isAgentMessage
                                  ? 'bg-[#D1FAE5] border-emerald-200 text-slate-900'
                                  : 'bg-cyan-600 border-cyan-600 text-white'
                          }`}
                        >
                          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                          <p className={`text-[11px] mt-2 ${isCustomer ? 'text-slate-500' : isSystem ? 'text-amber-800' : isAdmin && isAgentMessage ? 'text-slate-600' : 'text-cyan-100'}`}>
                            {new Date(message.created_at).toLocaleString()}
                          </p>

                          {message.custom_metadata?.knowledge_sources?.length ? (
                            <p className="text-[11px] mt-2 opacity-90">
                              Source: {message.custom_metadata.knowledge_sources.join(', ')}
                            </p>
                          ) : null}

                          {approval?.approval_id ? (
                            <div className="mt-3 rounded-xl border border-slate-200 bg-white text-slate-800 p-3">
                              <p className="text-xs font-semibold">Approval needed</p>
                              <p className="text-xs mt-1">{approval.request_summary}</p>
                              <p className="text-xs mt-1 text-slate-500">Approval ID: {approval.approval_id}</p>
                              {approvalStatus && approvalStatus !== 'pending' ? (
                                <p className="text-xs mt-1 text-emerald-700">
                                  Decision recorded: {approvalStatus}
                                  {approval.approved_by ? ` by ${approval.approved_by}` : ''}
                                </p>
                              ) : null}

                              {isAdmin && isApprovalPending ? (
                                <div className="mt-3 flex gap-2">
                                  <button
                                    onClick={() => handleApprovalDecision(approval.approval_id, 'approve')}
                                    className="btn-primary text-xs"
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
                              ) : isAdmin ? (
                                <p className="text-xs mt-2 text-slate-500">No action required.</p>
                              ) : (
                                <p className="text-xs mt-2 text-slate-500">
                                  {isApprovalPending ? 'Awaiting admin decision.' : 'Admin decision recorded.'}
                                </p>
                              )}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    )
                  })
                )}
              </div>

              <footer className="border-t border-slate-200 bg-white p-4">
                <div className="flex gap-3">
                  <textarea
                    value={draft}
                    onChange={(event) => setDraft(event.target.value)}
                    placeholder={placeholder}
                    className="w-full min-h-[84px] input"
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
              </footer>
            </>
          )}
        </section>
      </div>

      <section className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">Messages In Thread</p>
          <p className="text-3xl font-black text-slate-900 mt-2">{messages.length}</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-slate-500">Agent Mode</p>
          <p className="text-3xl font-black text-emerald-700 mt-2">{ticket?.chat_mode === 'agent' ? 'ON' : 'OFF'}</p>
        </div>
      </section>
    </div>
  )
}
