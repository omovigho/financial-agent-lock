import { useEffect, useState } from 'react'
import { approvalAPI } from '@/lib/api'

export default function ApprovalQueue() {
  const [approvals, setApprovals] = useState([])
  const [loading, setLoading] = useState(true)
  const [submittingId, setSubmittingId] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadApprovals()
  }, [])

  const loadApprovals = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await approvalAPI.listPending()
      setApprovals(res?.data?.approvals || [])
    } catch (err) {
      console.error('Failed to load approvals:', err)
      setError('Failed to load pending approvals.')
      setApprovals([])
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id) => {
    setSubmittingId(id)
    try {
      await approvalAPI.approve(id)
      await loadApprovals()
    } catch (error) {
      console.error('Approval failed:', error)
    } finally {
      setSubmittingId(null)
    }
  }

  const handleReject = async (id) => {
    setSubmittingId(id)
    try {
      await approvalAPI.reject(id)
      await loadApprovals()
    } catch (error) {
      console.error('Rejection failed:', error)
    } finally {
      setSubmittingId(null)
    }
  }

  return (
    <div className="card p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">⏳ Approvals Pending</h2>

      {error && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}
      
      <div className="space-y-4">
        {loading ? (
          <div className="text-center py-8 text-gray-500">Loading pending approvals...</div>
        ) : approvals.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <p className="text-lg mb-2">✨</p>
            <p>No pending approvals</p>
          </div>
        ) : (
          approvals.map((approval) => (
            <div key={approval.id} className="border border-yellow-200 bg-yellow-50 rounded-lg p-4">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-900">{approval.action}</h3>
                  <p className="text-sm text-gray-600">{approval.system}</p>
                </div>
                <span className="text-sm px-2 py-1 rounded bg-yellow-200 text-yellow-800">
                  Pending
                </span>
              </div>
              
              <pre className="text-xs bg-white p-2 rounded border border-yellow-200 mb-3 overflow-x-auto">
                {JSON.stringify(approval.request_data, null, 2)}
              </pre>
              
              <div className="flex gap-2">
                <button
                  onClick={() => handleApprove(approval.id)}
                  disabled={submittingId === approval.id}
                  className="btn-primary flex-1 disabled:opacity-50"
                >
                  {submittingId === approval.id ? 'Processing...' : '✅ Approve'}
                </button>
                <button
                  onClick={() => handleReject(approval.id)}
                  disabled={submittingId === approval.id}
                  className="btn-danger flex-1 disabled:opacity-50"
                >
                  {submittingId === approval.id ? 'Processing...' : '🚫 Reject'}
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
