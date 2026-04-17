import { useEffect, useMemo, useState } from 'react'
import AgentPanel from '@/components/AgentPanel'
import { erpAPI } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'

export default function ErpPage() {
  const currentYear = new Date().getFullYear()
  const [year, setYear] = useState(currentYear)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [summary, setSummary] = useState(null)
  const [purchaseOrders, setPurchaseOrders] = useState([])

  const years = useMemo(() => {
    const list = []
    for (let index = 0; index < 5; index += 1) {
      list.push(currentYear - index)
    }
    return list
  }, [currentYear])

  const loadErpData = async () => {
    setLoading(true)
    setError(null)

    try {
      const [summaryResponse, poResponse] = await Promise.all([
        erpAPI.getMySummary(year),
        erpAPI.getMyPurchaseOrders(year, 20),
      ])

      setSummary(summaryResponse.data || null)
      setPurchaseOrders(poResponse.data?.purchase_orders || [])
    } catch (err) {
      const detail = err?.response?.data?.detail || err?.message || 'Failed to load ERP records.'
      setError(detail)
      setSummary(null)
      setPurchaseOrders([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadErpData()
  }, [year])

  const statusEntries = Object.entries(summary?.status_counts || {})

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <h1 className="text-4xl font-bold text-gray-900 mb-2">📦 ERP Operations</h1>
        <div>
          <p className="text-gray-600">Enterprise resource planning with AI-assisted order management and inventory control.</p>
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

      <AgentPanel onActionExecuted={loadErpData} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-6">
          <div className="text-3xl mb-2">📋</div>
          <p className="text-gray-600 text-sm mb-1">Total Orders</p>
          <p className="text-2xl font-bold text-gray-900">{loading ? '...' : (summary?.total_orders ?? 0)}</p>
        </div>
        <div className="card p-6">
          <div className="text-3xl mb-2">📦</div>
          <p className="text-gray-600 text-sm mb-1">Pending Value</p>
          <p className="text-2xl font-bold text-gray-900">
            {loading ? '...' : formatCurrency(summary?.pending_order_value || 0)}
          </p>
        </div>
        <div className="card p-6">
          <div className="text-3xl mb-2">🏢</div>
          <p className="text-gray-600 text-sm mb-1">Vendors</p>
          <p className="text-2xl font-bold text-gray-900">{loading ? '...' : (summary?.vendor_count ?? 0)}</p>
        </div>
        <div className="card p-6">
          <div className="text-3xl mb-2">💰</div>
          <p className="text-gray-600 text-sm mb-1">Total Value</p>
          <p className="text-2xl font-bold text-gray-900">
            {loading ? '...' : formatCurrency(summary?.total_order_value || 0)}
          </p>
        </div>
      </div>

      <div className="card p-6">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Status Distribution</h3>
        {loading ? (
          <p className="text-gray-500">Loading status summary...</p>
        ) : statusEntries.length === 0 ? (
          <p className="text-gray-500">No status data for {year}.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
            {statusEntries.map(([status, count]) => (
              <div key={status} className="rounded-lg border border-gray-200 bg-gray-50 p-3">
                <p className="text-xs uppercase tracking-wide text-gray-500">{status}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">{count}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card p-6">
        <h3 className="text-xl font-bold text-gray-900 mb-4">Recent Purchase Orders</h3>
        {loading ? (
          <p className="text-gray-500">Loading purchase orders...</p>
        ) : purchaseOrders.length === 0 ? (
          <p className="text-gray-500">No purchase orders found for {year}.</p>
        ) : (
          <div className="space-y-3">
            {purchaseOrders.map((po) => (
              <div key={po.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg bg-gray-50">
                <div>
                  <p className="font-semibold text-gray-900">{po.po_number}</p>
                  <p className="text-sm text-gray-600">{po.vendor} • {po.description || 'No description'}</p>
                  <p className="text-xs text-gray-500 mt-1">{formatDateTime(po.created_at)} • {po.status}</p>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-gray-900">{formatCurrency(po.amount || 0)}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="card p-6">
          <p className="text-sm text-gray-600">Approved Value</p>
          <p className="text-2xl font-bold text-emerald-700 mt-2">
            {loading ? '...' : formatCurrency(summary?.approved_order_value || 0)}
          </p>
        </div>
        <div className="card p-6">
          <p className="text-sm text-gray-600">Scope</p>
          <p className="text-2xl font-bold text-gray-900 mt-2">
            {loading ? '...' : (summary?.scope === 'all' ? 'All Records' : 'My Records')}
          </p>
        </div>
      </div>
    </div>
  )
}
