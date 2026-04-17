'use client'

import { useState, useEffect } from 'react'
import type { Session } from '@/types'

interface SessionViewerProps {
  sessionId?: string
  onClose?: () => void
}

export default function SessionViewer({ sessionId, onClose }: SessionViewerProps) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(!!sessionId)
  const [expandedInteraction, setExpandedInteraction] = useState<number | null>(null)

  useEffect(() => {
    if (!sessionId) return

    // In a real app, this would fetch from sessionAPI.get(sessionId)
    // For demo purposes, we'll show sample data
    const sampleSession: Session = {
      session_id: sessionId,
      user_id: 1,
      context: {
        user_name: 'John Doe',
        department: 'Finance',
        role: 'analyst',
        approval_threshold: 10000,
      },
      conversation_history: [
        {
          type: 'user_input',
          content: 'Show me all transactions from the last quarter',
          timestamp: new Date(Date.now() - 600000).toISOString(),
        },
        {
          type: 'agent_response',
          content: 'Retrieved 47 transactions totaling $234,500',
          status: 'success',
          timestamp: new Date(Date.now() - 595000).toISOString(),
        },
        {
          type: 'user_input',
          content: 'Create a refund for transaction #TX-12345 in amount $5,000',
          timestamp: new Date(Date.now() - 300000).toISOString(),
        },
        {
          type: 'agent_response',
          content: 'Refund request created and sent for approval',
          status: 'pending',
          timestamp: new Date(Date.now() - 295000).toISOString(),
        },
      ],
      current_corpus: 'agent-lock',
      is_active: true,
      created_at: new Date(Date.now() - 3600000).toISOString(),
      last_activity_at: new Date(Date.now() - 60000).toISOString(),
      expires_at: new Date(Date.now() + 82800000).toISOString(), // 23 hours from now
    }

    setSession(sampleSession)
    setLoading(false)
  }, [sessionId])

  if (!sessionId) {
    return (
      <div className="card p-8 text-center text-gray-500">
        <p>Select a session to view details</p>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="card p-6">
        <p className="text-gray-500">Loading session details...</p>
      </div>
    )
  }

  if (!session) {
    return (
      <div className="card p-6 border-red-200 bg-red-50">
        <p className="text-red-700">Session not found</p>
      </div>
    )
  }

  const timeUntilExpiry = new Date(session.expires_at).getTime() - Date.now()
  const hoursRemaining = Math.floor(timeUntilExpiry / 3600000)

  return (
    <div className="space-y-6">
      {/* Session Header */}
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="text-2xl font-bold">Session Details</h2>
          <p className="text-gray-600 text-sm">{sessionId}</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700 text-2xl"
          >
            ✕
          </button>
        )}
      </div>

      {/* Session Metadata */}
      <div className="grid grid-cols-2 gap-4">
        <div className="card p-4">
          <p className="text-xs text-gray-600">Status</p>
          <p className="font-bold">{session.is_active ? '🟢 Active' : '⚪ Inactive'}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-600">Current Corpus</p>
          <p className="font-bold">{session.current_corpus}</p>
        </div>
        <div className="card p-4">
          <p className="text-xs text-gray-600">Created</p>
          <p className="font-bold">{new Date(session.created_at).toLocaleString()}</p>
        </div>
        <div className={`card p-4 ${hoursRemaining < 2 ? 'border-2 border-red-300 bg-red-50' : ''}`}>
          <p className="text-xs text-gray-600">Expires In</p>
          <p className={`font-bold ${hoursRemaining < 2 ? 'text-red-700' : ''}`}>
            {hoursRemaining}h remaining
          </p>
        </div>
      </div>

      {/* Context Data */}
      <div className="card p-4">
        <h3 className="font-bold mb-3">User Context</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          {Object.entries(session.context).map(([key, value]) => (
            <div key={key}>
              <p className="text-gray-600 text-xs">{key}</p>
              <p className="font-medium">{String(value)}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Conversation History */}
      <div>
        <h3 className="font-bold mb-3">Conversation History</h3>
        <div className="space-y-2">
          {session.conversation_history.length === 0 ? (
            <div className="card p-4 text-center text-gray-500">
              <p>No interactions yet</p>
            </div>
          ) : (
            session.conversation_history.map((interaction, idx) => {
              const isExpanded = expandedInteraction === idx
              const isUserInput = interaction.type === 'user_input'

              return (
                <div key={idx} className={`card overflow-hidden transition ${isUserInput ? 'bg-blue-50' : ''}`}>
                  <button
                    onClick={() => setExpandedInteraction(isExpanded ? null : idx)}
                    className="w-full p-4 text-left hover:bg-gray-100 transition flex justify-between items-start"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        {isUserInput ? (
                          <span className="text-xl">👤</span>
                        ) : (
                          <span className="text-xl">
                            {interaction.status === 'success' ? '✅' : interaction.status === 'pending' ? '⏳' : '❌'}
                          </span>
                        )}
                        <span className="font-semibold">
                          {isUserInput ? 'User Input' : 'Agent Response'}
                        </span>
                      </div>
                      <p className="text-sm text-gray-700 line-clamp-1">{interaction.content}</p>
                      <p className="text-xs text-gray-500 mt-1">
                        {new Date(interaction.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                    <span className="text-gray-400 ml-2">{isExpanded ? '▼' : '▶'}</span>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-gray-200 p-4 bg-gray-50">
                      <div className="font-mono text-xs bg-white p-3 rounded border border-gray-200 overflow-auto max-h-48">
                        <p className="whitespace-pre-wrap break-words">{interaction.content}</p>
                      </div>
                      {interaction.status && (
                        <div className="mt-2 text-xs">
                          <span className="font-medium">Status: </span>
                          <span className={
                            interaction.status === 'success' ? 'text-green-700' :
                            interaction.status === 'pending' ? 'text-yellow-700' :
                            'text-red-700'
                          }>
                            {interaction.status}
                          </span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>

      {/* Statistics */}
      <div className="card p-4 bg-gray-50">
        <h3 className="font-bold mb-3">Activity Statistics</h3>
        <div className="grid grid-cols-3 gap-2 text-sm">
          <div>
            <p className="text-gray-600 text-xs">Total Interactions</p>
            <p className="font-bold text-lg">{session.conversation_history.length}</p>
          </div>
          <div>
            <p className="text-gray-600 text-xs">Session Duration</p>
            <p className="font-bold text-lg">
              {Math.floor(
                (new Date(session.last_activity_at).getTime() - new Date(session.created_at).getTime()) / 60000
              )} min
            </p>
          </div>
          <div>
            <p className="text-gray-600 text-xs">Last Activity</p>
            <p className="font-bold text-sm">{new Date(session.last_activity_at).toLocaleTimeString()}</p>
          </div>
        </div>
      </div>
    </div>
  )
}
