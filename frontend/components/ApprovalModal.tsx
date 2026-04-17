'use client'

import { useEffect, useState } from 'react'
import { approvalAPI } from '@/lib/api'
import type { Approval } from '@/types'
import { formatDate } from '@/lib/utils'

interface ApprovalModalProps {
  isOpen: boolean
  approval: Approval | null
  onApprove: () => Promise<void>
  onDeny: () => Promise<void>
  onClose: () => void
}

export default function ApprovalModal({
  isOpen,
  approval,
  onApprove,
  onDeny,
  onClose,
}: ApprovalModalProps) {
  const [reasoning, setReasoning] = useState('')
  const [loading, setLoading] = useState(false)

  if (!isOpen || !approval) return null

  const handleApprove = async () => {
    setLoading(true)
    try {
      await onApprove()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  const handleDeny = async () => {
    setLoading(true)
    try {
      await onDeny()
      onClose()
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg max-w-lg w-full mx-4">
        <div className="p-6">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">Action Requires Approval</h2>

          <div className="space-y-4 mb-6 bg-gray-50 p-4 rounded-lg">
            <div>
              <span className="text-sm text-gray-600">Action: </span>
              <span className="font-semibold text-gray-900">{approval.action}</span>
            </div>

            <div>
              <span className="text-sm text-gray-600">System: </span>
              <span className="font-semibold text-gray-900">{approval.system}</span>
            </div>

            <div>
              <span className="text-sm text-gray-600">Created: </span>
              <span className="text-gray-900">{formatDate(approval.created_at)}</span>
            </div>

            <div>
              <span className="text-sm text-gray-600">Expires: </span>
              <span className="text-gray-900">{formatDate(approval.expires_at)}</span>
            </div>

            <div>
              <span className="text-sm text-gray-600">Details: </span>
              <pre className="text-xs bg-white p-2 rounded border border-gray-200 mt-1 overflow-auto max-h-32">
                {JSON.stringify(approval.request_data, null, 2)}
              </pre>
            </div>
          </div>

          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Approval Reasoning (optional)
            </label>
            <textarea
              value={reasoning}
              onChange={(e) => setReasoning(e.target.value)}
              placeholder="Explain your decision..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg"
              rows={3}
            />
          </div>

          <div className="flex space-x-3">
            <button
              onClick={handleApprove}
              disabled={loading}
              className="flex-1 btn-secondary disabled:opacity-50"
            >
              {loading ? 'Processing...' : '✓ Approve'}
            </button>
            <button
              onClick={handleDeny}
              disabled={loading}
              className="flex-1 btn-danger disabled:opacity-50"
            >
              {loading ? 'Processing...' : '✕ Deny'}
            </button>
            <button
              onClick={onClose}
              disabled={loading}
              className="flex-1 btn-outline disabled:opacity-50"
            >
              Cancel
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
