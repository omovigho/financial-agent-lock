import { useEffect, useMemo, useState } from 'react'
import AgentPanel from '@/components/AgentPanel'
import { financialAPI } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'

export default function FinancialPage() {
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [transactions, setTransactions] = useState([])

  const years = useMemo(() => {
    const list = []
    for (let index = 0; index < 5; index += 1) {
      list.push(currentYear - index)
    }
    return list
  }, [currentYear])

  const loadFinancialData = async () => {
    setLoading(true)
    setError(null)

    try {
      const [summaryResponse, transactionsResponse] = await Promise.all([
        financialAPI.getMySummary(year),
        financialAPI.getMyTransactions(year, 20),
      ])

      setSummary(summaryResponse.data || null)
      setTransactions(transactionsResponse.data?.transactions || [])
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to load financial records.'
      setError(detail)
      setSummary(null)
      setTransactions([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadFinancialData()
  }, [year])

  const topCategoriesLabel = (summary?.top_categories || [])
    .map((entry) => `${entry.category} (${entry.count})`)
    .join(', ')

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">💼 Financial Operations</h1>
        <div>
          <p className="text-gray-600">Manage financial transactions with AI-powered analysis and approval workflows.</p>
          <div className="mt-3 flex items-center gap-2">
            <label className="text-sm text-gray-600">Year</label>
            <select
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
              className="input max-w-[140px]"
            >
              {years.map((value) => (
                <option key={value} value={value}>{value}</option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-red-700 text-sm">{error}</div>
      ) : null}

      <AgentPanel onActionExecuted={loadFinancialData} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="card p-6">
          <p className="text-sm text-gray-600">Total Transactions</p>
          <p className="text-3xl font-bold text-gray-900 mt-2">
            {loading ? '...' : (summary?.transaction_count ?? 0)}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-gray-600">Total Inflow</p>
          <p className="text-3xl font-bold text-emerald-600 mt-2">
            {loading ? '...' : formatCurrency(summary?.total_inflow || 0)}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-gray-600">Total Outflow</p>
          <p className="text-3xl font-bold text-rose-600 mt-2">
            {loading ? '...' : formatCurrency(summary?.total_outflow || 0)}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="card p-6">
          <p className="text-sm text-gray-600">Net Position</p>
          <p className={`text-3xl font-bold mt-2 ${(summary?.net_position || 0) >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
            {loading ? '...' : formatCurrency(summary?.net_position || 0)}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-gray-600">Top Categories</p>
          <p className="text-sm text-gray-900 mt-2">
            {loading ? 'Loading...' : (topCategoriesLabel || 'No category data for selected year.')}
          </p>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Recent Transactions</h3>
        {loading ? (
          <p className="text-gray-500">Loading transactions...</p>
        ) : transactions.length === 0 ? (
          <p className="text-gray-500">No transactions found for {year}.</p>
        ) : (
          <div className="space-y-3">
            {transactions.map((txn) => (
              <div key={txn.id} className="rounded-lg border border-gray-200 bg-gray-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-semibold text-gray-900">{txn.description}</p>
                    <p className="text-xs text-gray-500 mt-1">
                      {txn.reference} • {txn.category} • {txn.status}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold text-gray-900">{formatCurrency(txn.amount || 0)}</p>
                    <p className="text-xs text-gray-500 mt-1">{formatDateTime(txn.date)}</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
