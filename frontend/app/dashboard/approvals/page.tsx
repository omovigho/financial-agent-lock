'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import { approvalAPI } from '@/lib/api'
import ApprovalModal from '@/components/ApprovalModal'
import type { Approval } from '@/types'
import { formatDate } from '@/lib/utils'

export default function ApprovalsPage() {
  const { user } = useAuthStore()
  const router = useRouter()
  const [approvals, setApprovals] = useState<Approval[]>([])
  const [filterStatus, setFilterStatus] = useState<string | null>(null)
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [showModal, setShowModal] = useState(false)

  useEffect(() => {
    // Redirect if not admin
    if (user && user.role !== 'admin') {
      router.push('/dashboard')
    } else {
      loadApprovals()
    }
  }, [filterStatus, user, router])

  const loadApprovals = async () => {
    try {
      const res = await approvalAPI.listAll(filterStatus || undefined)
      setApprovals(res.data.approvals)
    } catch (error) {
      console.error('Failed to load approvals:', error)
    }
  }

  const handleApprove = async () => {
    if (!selectedApproval) return
    try {
      await approvalAPI.resolve(selectedApproval.id, 'approved')
      await loadApprovals()
    } catch (error) {
      console.error('Failed to approve:', error)
    }
  }

  const handleDeny = async () => {
    if (!selectedApproval) return
    try {
      await approvalAPI.resolve(selectedApproval.id, 'denied')
      await loadApprovals()
    } catch (error) {
      console.error('Failed to deny:', error)
    }
  }

  if (!user || user.role !== 'admin') {
    return (
      <div className="p-6 max-w-7xl mx-auto">
        <div className="card p-6 text-center">
          <h1 className="text-2xl font-bold text-gray-900 mb-4">Access Denied</h1>
          <p className="text-gray-600">You don&apos;t have permission to access this page.</p>
        </div>
      </div>
    )
  }

  const statusCounts = {
    pending: approvals.filter((a) => a.status === 'pending').length,
    approved: approvals.filter((a) => a.status === 'approved').length,
    denied: approvals.filter((a) => a.status === 'denied').length,
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">✅ Approval Workflow</h1>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card p-6">
          <p className="text-gray-600 text-sm">Pending</p>
          <p className="text-3xl font-bold text-yellow-600 mt-2">{statusCounts.pending}</p>
        </div>
        <div className="card p-6">
          <p className="text-gray-600 text-sm">Approved</p>
          <p className="text-3xl font-bold text-green-600 mt-2">{statusCounts.approved}</p>
        </div>
        <div className="card p-6">
          <p className="text-gray-600 text-sm">Denied</p>
          <p className="text-3xl font-bold text-red-600 mt-2">{statusCounts.denied}</p>
        </div>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-2">
        <button
          onClick={() => setFilterStatus(null)}
          className={`btn ${filterStatus === null ? 'btn-primary' : 'btn-outline'}`}
        >
          All
        </button>
        <button
          onClick={() => setFilterStatus('pending')}
          className={`btn ${filterStatus === 'pending' ? 'btn-primary' : 'btn-outline'}`}
        >
          Pending
        </button>
        <button
          onClick={() => setFilterStatus('approved')}
          className={`btn ${filterStatus === 'approved' ? 'btn-primary' : 'btn-outline'}`}
        >
          Approved
        </button>
        <button
          onClick={() => setFilterStatus('denied')}
          className={`btn ${filterStatus === 'denied' ? 'btn-primary' : 'btn-outline'}`}
        >
          Denied
        </button>
      </div>

      {/* Approval List */}
      <div className="card p-6">
        {approvals.length === 0 ? (
          <p className="text-center text-gray-500 py-8">No approvals to display</p>
        ) : (
          <div className="space-y-3">
            {approvals.map((approval) => (
              <div
                key={approval.id}
                className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 cursor-pointer transition"
                onClick={() => {
                  setSelectedApproval(approval)
                  setShowModal(true)
                }}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-3">
                      <p className="font-semibold text-gray-900">{approval.action}</p>
                      <span className={`badge badge-${approval.status === 'approved' ? 'success' : approval.status === 'denied' ? 'danger' : 'warning'}`}>
                        {approval.status}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-2">System: {approval.system}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      Created: {formatDate(approval.created_at)}
                    </p>
                    {approval.approved_by && (
                      <p className="text-xs text-gray-500 mt-1">
                        Approved by: {approval.approved_by}
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-600">ID: {approval.id}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Modal */}
      <ApprovalModal
        isOpen={showModal}
        approval={selectedApproval}
        onApprove={handleApprove}
        onDeny={handleDeny}
        onClose={() => {
          setShowModal(false)
          setSelectedApproval(null)
        }}
      />
    </div>
  )
}
