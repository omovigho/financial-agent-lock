'use client'

import { useState, useEffect } from 'react'
import { approvalAPI } from '@/lib/api'
import type { Approval } from '@/types'

export default function ApprovalQueue() {
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [actionReason, setActionReason] = useState('')
  const [processingId, setProcessingId] = useState<number | null>(null)

  useEffect(() => {
    loadApprovals()
  }, [])

  const loadApprovals = async () => {
    try {
      setLoading(true)
      const res = await approvalAPI.listPending()
      const data = res.data
      setApprovals(Array.isArray(data) ? data : data.approvals || [])
    } catch (error) {
      console.error('Failed to load approvals:', error)
      setApprovals([])
    } finally {
      setLoading(false)
    }
  }

  const handleApprove = async (id: number) => {
    setProcessingId(id)
    try {
      await approvalAPI.approve(id, actionReason)
      setApprovals(approvals.filter(a => a.id !== id))
      setSelectedId(null)
      setActionReason('')
    } catch (error) {
      alert('Failed to approve: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setProcessingId(null)
    }
  }

  const handleReject = async (id: number) => {
    setProcessingId(id)
    try {
      await approvalAPI.reject(id, actionReason)
      setApprovals(approvals.filter(a => a.id !== id))
      setSelectedId(null)
      setActionReason('')
    } catch (error) {
      alert('Failed to reject: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setProcessingId(null)
    }
  }

  const getSystemColor = (system: string) => {
    switch (system) {
      case 'financial':
        return 'text-red-700 bg-red-50 border-red-200'
      case 'erp':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200'
      case 'support':
        return 'text-green-700 bg-green-50 border-green-200'
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200'
    }
  }

  if (loading) {
    return <div className="card p-6"><p className="text-gray-500">Loading approvals...</p></div>
  }

  return (
    <div className="space-y-6">
      {/* Summary */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-sm text-blue-900">
          <strong>{approvals.length}</strong> pending approval{approvals.length !== 1 ? 's' : ''}
        </p>
      </div>

      {/* Approvals List */}
      {approvals.length === 0 ? (
        <div className="card p-6 text-center">
          <p className="text-gray-500">✅ All caught up! No pending approvals.</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {approvals.map((approval) => (
            <div key={approval.id} className={`card p-4 border-2 cursor-pointer transition ${
              selectedId === approval.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-300'
            }`} onClick={() => setSelectedId(approval.id)}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="font-semibold text-gray-900">{approval.action}</h3>
                    <span className={`px-2 py-1 rounded text-xs font-medium border ${getSystemColor(approval.system)}`}>
                      {approval.system.toUpperCase()}
                    </span>
                  </div>
                  
                  <div className="text-sm text-gray-600 mb-3">
                    Requested {new Date(approval.created_at).toLocaleString()}
                  </div>

                  {/* Request Details */}
                  {selectedId === approval.id && (
                    <div className="mt-4 p-3 bg-white border border-gray-200 rounded">
                      <p className="text-xs font-medium text-gray-700 mb-2">Request Details:</p>
                      <pre className="text-xs overflow-auto max-h-32 bg-gray-50 p-2 rounded">
                        {JSON.stringify(approval.request_data, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                <div className="text-xs text-gray-500 flex-shrink-0">
                  ID: {approval.id}
                </div>
              </div>

              {/* Action Buttons */}
              {selectedId === approval.id && (
                <div className="mt-4 space-y-3 border-t border-gray-200 pt-4">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">Reason (optional)</label>
                    <textarea
                      value={actionReason}
                      onChange={(e) => setActionReason(e.target.value)}
                      placeholder="Enter approval reason..."
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded"
                      rows={2}
                    />
                  </div>

                  <div className="flex gap-2">
                    <button
                      onClick={() => handleApprove(approval.id)}
                      disabled={processingId === approval.id}
                      className="flex-1 px-4 py-2 bg-green-600 text-white rounded font-medium text-sm hover:bg-green-700 disabled:opacity-50"
                    >
                      {processingId === approval.id ? '⏳ Processing...' : '✅ Approve'}
                    </button>
                    <button
                      onClick={() => handleReject(approval.id)}
                      disabled={processingId === approval.id}
                      className="flex-1 px-4 py-2 bg-red-600 text-white rounded font-medium text-sm hover:bg-red-700 disabled:opacity-50"
                    >
                      {processingId === approval.id ? '⏳ Processing...' : '❌ Reject'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
