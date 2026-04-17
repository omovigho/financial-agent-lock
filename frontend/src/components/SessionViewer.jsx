import { useState, useEffect } from 'react'
import { sessionAPI } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'

export default function SessionViewer() {
  const [sessions, setSessions] = useState([])
  const [selectedSession, setSelectedSession] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadSessions()
  }, [])

  const loadSessions = async () => {
    try {
      const res = await sessionAPI.list()
      setSessions(res.data)
    } catch (error) {
      console.error('Failed to load sessions:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async (sessionId) => {
    try {
      await sessionAPI.delete(sessionId)
      setSessions(sessions.filter(s => s.id !== sessionId))
      if (selectedSession?.id === sessionId) {
        setSelectedSession(null)
      }
    } catch (error) {
      console.error('Failed to delete session:', error)
    }
  }

  if (loading) {
    return <div className="card p-6 text-gray-500">Loading sessions...</div>
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <div className="lg:col-span-1">
        <div className="card p-4">
          <h3 className="font-semibold text-gray-900 mb-3">Sessions</h3>
          <div className="space-y-2 max-h-96 overflow-y-auto">
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-500">No sessions</p>
            ) : (
              sessions.map(session => (
                <button
                  key={session.id}
                  onClick={() => setSelectedSession(session)}
                  className={`w-full text-left p-2 rounded text-sm transition-colors ${
                    selectedSession?.id === session.id
                      ? 'bg-blue-50 border border-blue-200'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  <div className="font-medium text-gray-900 truncate">{session.id}</div>
                  <div className="text-xs text-gray-500">{formatDateTime(session.created_at)}</div>
                </button>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="lg:col-span-2">
        {selectedSession ? (
          <div className="card p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold text-gray-900">Session Details</h3>
              <button
                onClick={() => handleDelete(selectedSession.id)}
                className="text-red-600 hover:text-red-700 text-sm"
              >
                Delete
              </button>
            </div>
            <div className="space-y-4">
              <div>
                <label className="label">Session ID</label>
                <input type="text" value={selectedSession.id} disabled className="input w-full" />
              </div>
              <div>
                <label className="label">Created</label>
                <input type="text" value={formatDateTime(selectedSession.created_at)} disabled className="input w-full" />
              </div>
              <div>
                <label className="label">Context</label>
                <pre className="bg-gray-50 p-3 rounded border border-gray-200 text-xs overflow-auto max-h-48">
                  {JSON.stringify(selectedSession.context || {}, null, 2)}
                </pre>
              </div>
              {selectedSession.history && selectedSession.history.length > 0 && (
                <div>
                  <label className="label">Interaction History</label>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {selectedSession.history.map((interaction, idx) => (
                      <div key={idx} className="bg-gray-50 p-2 rounded text-sm">
                        <p className="font-medium">{interaction.action}</p>
                        <p className="text-gray-600 text-xs">{formatDateTime(interaction.timestamp)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="card p-6 text-center text-gray-500">
            <p>Select a session to view details</p>
          </div>
        )}
      </div>
    </div>
  )
}
