import { useState } from 'react'
import ApprovalQueue from '@/components/ApprovalQueue'

export default function ApprovalsPage() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">✅ Approvals</h1>
        <p className="text-gray-600">Review and approve pending AI agent actions that require human oversight.</p>
      </div>

      <ApprovalQueue />
    </div>
  )
}
