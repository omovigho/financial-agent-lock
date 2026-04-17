'use client'

import { useState, useEffect } from 'react'
import AgentPanel from '@/components/AgentPanel'
import TokenDisplay from '@/components/TokenDisplay'
import ApprovalModal from '@/components/ApprovalModal'
import { approvalAPI, policyAPI } from '@/lib/api'
import { useAuthStore } from '@/lib/store'
import type { Approval, AgentResponse } from '@/types'
import { formatDate } from '@/lib/utils'

export default function DashboardPage() {
  const { user } = useAuthStore()
  const [pendingApprovals, setPendingApprovals] = useState<Approval[]>([])
  const [selectedApproval, setSelectedApproval] = useState<Approval | null>(null)
  const [showApprovalModal, setShowApprovalModal] = useState(false)
  const [policyStats, setPolicyStats] = useState<any>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      const [approvalsRes, policyRes] = await Promise.all([
        approvalAPI.listPending(),
        policyAPI.dashboard(),
      ])

      setPendingApprovals(approvalsRes.data?.approvals || [])
      setPolicyStats(policyRes.data || {})
    } catch (error) {
      console.error('Failed to load data:', error)
      setPendingApprovals([])
      setPolicyStats({})
    }
  }

  const handleApprovalSelect = (approval: Approval) => {
    setSelectedApproval(approval)
    setShowApprovalModal(true)
  }

  const handleApprovalApprove = async () => {
    if (!selectedApproval) return
    try {
      await approvalAPI.resolve(selectedApproval.id, 'approved')
      await loadData()
    } catch (error) {
      console.error('Failed to approve:', error)
    }
  }

  const handleApprovalDeny = async () => {
    if (!selectedApproval) return
    try {
      await approvalAPI.resolve(selectedApproval.id, 'denied')
      await loadData()
    } catch (error) {
      console.error('Failed to deny:', error)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Welcome Header */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-gray-900">
          Welcome back, {user?.name}! 👋
        </h1>
        <p className="text-gray-600 mt-2">
          Secure AI agent platform for financial, customer support, and ERP operations
        </p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Pending Approvals</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {pendingApprovals.length}
              </p>
            </div>
            <span className="text-4xl">⏳</span>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Active Systems</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {policyStats?.systems?.length || 0}
              </p>
            </div>
            <span className="text-4xl">🛡️</span>
          </div>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">Total Policies</p>
              <p className="text-3xl font-bold text-gray-900 mt-2">
                {policyStats?.total_policies || 0}
              </p>
            </div>
            <span className="text-4xl">📋</span>
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Panel */}
        <div className="lg:col-span-2">
          <AgentPanel onActionExecuted={loadData} />
        </div>

        {/* Tokens */}
        <div>
          <TokenDisplay />
        </div>
      </div>

      {/* Pending Approvals */}
      {pendingApprovals.length > 0 && (
        <div className="mt-8 card p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">
            Pending Approvals ({pendingApprovals.length})
          </h2>

          <div className="space-y-3">
            {pendingApprovals.map((approval) => (
              <div
                key={approval.id}
                className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:bg-gray-100 cursor-pointer"
                onClick={() => handleApprovalSelect(approval)}
              >
                <div className="flex justify-between items-start">
                  <div>
                    <p className="font-semibold text-gray-900">{approval.action}</p>
                    <p className="text-sm text-gray-600 mt-1">
                      System: {approval.system}
                    </p>
                    <p className="text-xs text-gray-500 mt-2">
                      Created: {formatDate(approval.created_at)}
                    </p>
                  </div>
                  <span className="badge badge-warning">Pending</span>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={() => handleApprovalSelect(pendingApprovals[0])}
            className="w-full mt-4 btn-secondary"
          >
            Review Approvals
          </button>
        </div>
      )}

      {/* Approval Modal */}
      <ApprovalModal
        isOpen={showApprovalModal}
        approval={selectedApproval}
        onApprove={handleApprovalApprove}
        onDeny={handleApprovalDeny}
        onClose={() => {
          setShowApprovalModal(false)
          setSelectedApproval(null)
        }}
      />
    </div>
  )
}
