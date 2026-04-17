import { useState } from 'react'
import { policyAPI } from '@/lib/api'

export default function PolicyPage() {
  const [policies, setPolicies] = useState([
    {
      id: 1,
      name: 'Financial Transaction Limit',
      action: 'create_transaction',
      system: 'financial',
      rule: 'amount <= 50000',
      description: 'Transactions cannot exceed $50,000 without approval',
    },
    {
      id: 2,
      name: 'Refund Limit',
      action: 'create_refund',
      system: 'support',
      rule: 'amount <= 1000',
      description: 'Refunds above $1,000 require manager approval',
    },
  ])
  const [newPolicy, setNewPolicy] = useState({
    name: '',
    action: '',
    system: 'financial',
    rule: '',
  })
  const [showForm, setShowForm] = useState(false)

  const handleAddPolicy = () => {
    if (newPolicy.name && newPolicy.action && newPolicy.rule) {
      setPolicies([...policies, { id: policies.length + 1, ...newPolicy }])
      setNewPolicy({ name: '', action: '', system: 'financial', rule: '' })
      setShowForm(false)
    }
  }

  const handleDeletePolicy = (id) => {
    setPolicies(policies.filter(p => p.id !== id))
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">🛡️ Policy Management</h1>
        <p className="text-gray-600">Define and manage AI agent operation policies and approval thresholds.</p>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Active Policies</h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="btn-primary"
          >
            + Add Policy
          </button>
        </div>

        {showForm && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-4">
            <h3 className="font-semibold text-gray-900">Create New Policy</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="label">Policy Name</label>
                <input
                  type="text"
                  value={newPolicy.name}
                  onChange={(e) => setNewPolicy({ ...newPolicy, name: e.target.value })}
                  className="input w-full"
                  placeholder="e.g., Daily Limit"
                />
              </div>
              <div>
                <label className="label">Action</label>
                <input
                  type="text"
                  value={newPolicy.action}
                  onChange={(e) => setNewPolicy({ ...newPolicy, action: e.target.value })}
                  className="input w-full"
                  placeholder="e.g., create_refund"
                />
              </div>
              <div>
                <label className="label">System</label>
                <select
                  value={newPolicy.system}
                  onChange={(e) => setNewPolicy({ ...newPolicy, system: e.target.value })}
                  className="input w-full"
                >
                  <option value="financial">Financial</option>
                  <option value="support">Support</option>
                  <option value="erp">ERP</option>
                </select>
              </div>
              <div>
                <label className="label">Rule</label>
                <input
                  type="text"
                  value={newPolicy.rule}
                  onChange={(e) => setNewPolicy({ ...newPolicy, rule: e.target.value })}
                  className="input w-full"
                  placeholder="e.g., amount <= 50000"
                />
              </div>
            </div>
            <div className="flex gap-2">
              <button onClick={handleAddPolicy} className="btn-primary flex-1">
                ✅ Create Policy
              </button>
              <button onClick={() => setShowForm(false)} className="btn-secondary flex-1">
                ✕ Cancel
              </button>
            </div>
          </div>
        )}

        <div className="space-y-3">
          {policies.map(policy => (
            <div key={policy.id} className="border border-gray-200 rounded-lg p-4">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-gray-900">{policy.name}</h3>
                  <p className="text-sm text-gray-600">{policy.description}</p>
                </div>
                <button
                  onClick={() => handleDeletePolicy(policy.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  🗑️
                </button>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <span className="px-2 py-1 rounded bg-gray-100 text-gray-700">{policy.system}</span>
                <span className="px-2 py-1 rounded bg-blue-50 text-blue-700">{policy.action}</span>
                <code className="text-gray-600 font-mono text-xs">{policy.rule}</code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
