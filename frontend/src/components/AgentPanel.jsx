import { useState } from 'react'
import { agentAPI } from '@/lib/api'

export default function AgentPanel({ onActionExecuted }) {
  const [query, setQuery] = useState('')
  const [advancedMode, setAdvancedMode] = useState(false)
  const [system, setSystem] = useState('financial')
  const [action, setAction] = useState('read_transactions')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)

  const handleExecute = async () => {
    if (!query.trim()) return

    setLoading(true)
    try {
      const res = await agentAPI.execute(query, system, action, {}, true)
      console.log('[AgentPanel.jsx] raw execute response:', res.data)
      const data = res.data
      let normalized = data
      if (data && typeof data === 'object') {
        if (!('message' in data) && data.data && typeof data.data === 'object' && 'message' in data.data) {
          normalized = data.data
        }
      }
      setResult(normalized)
      onActionExecuted?.(normalized)
    } catch (error) {
      setResult({
        status: 'failure',
        decision: 'error',
        requirements: {
          error: error instanceof Error ? error.message : 'Unknown error',
        },
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">🤖 Agent Command Center</h2>
        <button
          onClick={() => setAdvancedMode(!advancedMode)}
          className={`text-sm px-3 py-1 rounded ${
            advancedMode
              ? 'bg-blue-100 text-blue-700 border border-blue-300'
              : 'bg-gray-100 text-gray-600 border border-gray-300'
          }`}
        >
          {advancedMode ? '✨ Advanced Mode (ON)' : '✨ Advanced Mode'}
        </button>
      </div>

      <div className="space-y-4">
        {/* Natural Language Input - DEFAULT */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            What would you like the agent to do?
          </label>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Example: Show me all transactions from last month, or Create a refund for order #12345..."
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-base"
            rows={3}
            disabled={loading}
          />
          <p className="text-xs text-gray-500 mt-1">
            💡 Describe your request in natural language. The agent will understand and execute it.
          </p>
        </div>

        {/* Advanced Mode Controls - HIDDEN BY DEFAULT */}
        {advancedMode && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-4">
            <h3 className="font-semibold text-blue-900 mb-3">Advanced Options</h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="label">System</label>
                <select
                  value={system}
                  onChange={(e) => setSystem(e.target.value)}
                  className="input w-full"
                >
                  <option value="financial">Financial</option>
                  <option value="support">Support</option>
                  <option value="erp">ERP</option>
                </select>
              </div>
              <div>
                <label className="label">Action</label>
                <select
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  className="input w-full"
                >
                  <option value="read_transactions">Read Transactions</option>
                  <option value="create_refund">Create Refund</option>
                  <option value="create_purchase_order">Create PO</option>
                </select>
              </div>
            </div>
          </div>
        )}

        {/* Execute Button */}
        <button
          onClick={handleExecute}
          disabled={loading || !query.trim()}
          className="btn-primary w-full disabled:opacity-50"
        >
          {loading ? 'Executing...' : '▶️ Execute Agent'}
        </button>

        {/* Result Display */}
        {result && (
          <div className={`mt-4 p-4 rounded-lg border ${
              result?.status === 'success' 
                ? 'bg-green-50 border-green-200' 
                : 'bg-red-50 border-red-200'
            }`}>
              <h4 className="font-semibold mb-2">Agent Response</h4>

              <div className="mb-3">
                <p className="text-lg font-semibold text-gray-900">
                  {result?.message ?? 'No message returned.'}
                </p>
              </div>

              <div>
                <h5 className="text-sm text-gray-600 mb-2">Summary</h5>
                {result?.summary ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    {Object.entries(result.summary).map(([k, v]) => {
                      const key = k.replace(/_/g, ' ')
                      const isCurrency = /income|expenses|total|balance/i.test(k)
                      const displayValue = (typeof v === 'number' && isCurrency)
                        ? new Intl.NumberFormat(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(v)
                        : String(v)

                      return (
                        <div key={k} className="p-3 bg-white border rounded">
                          <div className="text-xs text-gray-500">{key}</div>
                          <div className="mt-1 font-medium text-gray-900">{displayValue}</div>
                        </div>
                      )
                    })}
                  </div>
                ) : (
                  <div className="text-sm text-gray-500">No summary available.</div>
                )}
              </div>
            </div>
        )}
      </div>
    </div>
  )
}
