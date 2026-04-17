'use client'

import { useState } from 'react'
import { agentAPI } from '@/lib/api'
import type { AgentResponse } from '@/types'

interface AgentPanelProps {
  onActionExecuted?: (result: AgentResponse) => void
}

export default function AgentPanel({ onActionExecuted }: AgentPanelProps) {
  const [query, setQuery] = useState('')
  const [advancedMode, setAdvancedMode] = useState(false)
  const [system, setSystem] = useState('financial')
  const [action, setAction] = useState('read_transactions')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AgentResponse | null>(null)

  const handleExecute = async () => {
    if (!query.trim()) return

    setLoading(true)
    try {
      const res = await agentAPI.execute(query, system, action, {}, true)
      console.log('[AgentPanel] raw execute response:', res.data)
      // Normalize: prefer compact {message, summary}, else extract from data
      const data = res.data
      let normalized: any = data
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
                <label className="block text-sm font-medium text-gray-700 mb-2">System</label>
                <select
                  value={system}
                  onChange={(e) => setSystem(e.target.value)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm"
                  disabled={loading}
                >
                  <option value="financial">💰 Financial</option>
                  <option value="support">🎧 Support</option>
                  <option value="erp">📦 ERP</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">Action</label>
                <input
                  type="text"
                  value={action}
                  onChange={(e) => setAction(e.target.value)}
                  placeholder="e.g., read_transactions"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm"
                  disabled={loading}
                />
              </div>
            </div>
          </div>
        )}

        {/* Execute Button */}
        <button
          onClick={handleExecute}
          disabled={!query.trim() || loading}
          className="w-full btn-primary disabled:opacity-50 disabled:cursor-not-allowed py-3 font-semibold"
        >
          {loading ? (
            <>
              <span className="inline-block animate-spin mr-2">⚙️</span>
              Agent is working...
            </>
          ) : (
            '▶️ Execute'
          )}
        </button>
      </div>

      {/* Result Display: show only message + summary with styling */}
      {result && (
        <div className="mt-6 p-6 bg-white rounded-2xl border border-gray-100 shadow-sm">
          <h3 className="font-semibold text-gray-900 mb-4">Agent Response</h3>

          {/* Message */}
          <div className="mb-4">
            <p className="text-lg md:text-2xl font-semibold text-gray-900 leading-relaxed">
              {typeof result === 'object' && 'message' in result
                ? (result as any).message
                : result?.data && typeof result.data === 'object' && 'message' in result.data
                  ? (result.data as any).message
                  : 'No response message.'}
            </p>
          </div>

          {/* Summary Grid */}
          <div>
            <h4 className="text-sm text-gray-500 mb-2">Summary</h4>
            {((result && (result as any).summary) || (result?.data && (result.data as any).summary)) ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {Object.entries(((result && (result as any).summary) ? (result as any).summary : (result.data as any).summary)).map(([k, v]) => {
                  const key = k.replace(/_/g, ' ')
                  const isCurrency = /income|expenses|total|balance/i.test(k)
                  const displayValue = typeof v === 'number' && isCurrency
                    ? v.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 2 })
                    : String(v)

                  return (
                    <div key={k} className="p-3 bg-gray-50 border border-gray-100 rounded-lg">
                      <div className="text-xs text-gray-500">{key}</div>
                      <div className="mt-1 font-medium text-gray-900">{displayValue}</div>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div className="p-3 bg-gray-50 border border-gray-100 rounded-lg text-sm text-gray-600">No summary available.</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
