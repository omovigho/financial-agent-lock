'use client'

import AgentPanel from '@/components/AgentPanel'

export default function ERPPage() {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">📦 ERP Operations</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Panel */}
        <div className="lg:col-span-2">
          <AgentPanel />
        </div>

        {/* Quick Info */}
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">ERP Features</h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>✓ Check inventory levels</li>
              <li>✓ Detect low stock</li>
              <li>⚠ Create PO (approval required)</li>
            </ul>
          </div>

          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Approval Policy</h3>
            <p className="text-sm text-gray-700">
              Purchase orders over <strong>$5,000</strong> require approval
            </p>
            <p className="text-xs text-gray-500 mt-3">
              Automatic approval for smaller purchases to improve efficiency
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
