import { useState } from 'react'

export default function ApprovalModal({ approval, onApprove, onReject, onClose }) {
  const [reason, setReason] = useState('')

  const handleApprove = () => {
    onApprove(approval.id, reason)
  }

  const handleReject = () => {
    onReject(approval.id, reason)
  }

  if (!approval) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-lg max-w-md w-full mx-4">
        <div className="p-6">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{approval.action}</h2>
              <p className="text-gray-600">{approval.system}</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-xl"
            >
              ✕
            </button>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg mb-4">
            <h3 className="font-semibold text-gray-900 mb-2">Request Details</h3>
            <pre className="text-xs whitespace-pre-wrap text-gray-700">
              {JSON.stringify(approval.request_data, null, 2)}
            </pre>
          </div>

          <div className="mb-4">
            <label className="label">Optional Reason</label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Add a comment (optional)..."
              className="w-full input"
              rows={3}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              className="btn-primary flex-1"
            >
              ✅ Approve
            </button>
            <button
              onClick={handleReject}
              className="btn-danger flex-1"
            >
              🚫 Reject
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
