import { useState, useEffect } from 'react'
import { auditAPI } from '@/lib/api'
import { formatDateTime } from '@/lib/utils'

export default function AuditPage() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [filter, setFilter] = useState('all')

  useEffect(() => {
    loadLogs()
  }, [])

  const loadLogs = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await auditAPI.listLogs(undefined, undefined, 200)
      setLogs(response?.data?.logs || [])
    } catch (err) {
      console.error('Failed to load audit logs:', err)
      setError('Failed to load audit logs.')
      setLogs([])
    } finally {
      setLoading(false)
    }
  }

  const systemCount = {
    all: logs.length,
    financial: logs.filter(l => l.system === 'financial').length,
    support: logs.filter(l => l.system === 'support').length,
    erp: logs.filter(l => l.system === 'erp').length,
  }

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.system === filter)

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">📋 Audit Logs</h1>
        <p className="text-gray-600">Complete audit trail of all AI agent actions and system operations.</p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Filter Buttons */}
      <div className="flex flex-wrap gap-2">
        {(['all', 'financial', 'support', 'erp']).map(system => (
          <button
            key={system}
            onClick={() => setFilter(system)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === system
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-900 hover:bg-gray-200'
            }`}
          >
            {system === 'all' ? 'All' : system.charAt(0).toUpperCase() + system.slice(1)}
          </button>
        ))}
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card p-4 text-center">
          <p className="text-gray-600 text-sm">Total Events</p>
          <p className="text-3xl font-bold text-gray-900">{systemCount.all}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-gray-600 text-sm">Financial</p>
          <p className="text-3xl font-bold text-blue-600">{systemCount.financial}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-gray-600 text-sm">Support</p>
          <p className="text-3xl font-bold text-purple-600">{systemCount.support}</p>
        </div>
        <div className="card p-4 text-center">
          <p className="text-gray-600 text-sm">ERP</p>
          <p className="text-3xl font-bold text-green-600">{systemCount.erp}</p>
        </div>
      </div>

      {/* Audit Log Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full max-w-7xl">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">User</th>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">Action</th>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">System</th>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">Status</th>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">Time</th>
                <th className="text-left py-3 px-6 text-sm font-semibold text-gray-900">Details</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} className="py-8 px-6 text-center text-gray-500">
                    Loading audit logs...
                  </td>
                </tr>
              ) : filteredLogs.map(log => (
                <tr key={log.id} className="border-b border-gray-200 hover:bg-gray-50">
                  <td className="py-3 px-6 text-sm text-gray-900">{`User ${log.user_id}`}</td>
                  <td className="py-3 px-6 text-sm text-gray-600">{log.action}</td>
                  <td className="py-3 px-6 text-sm">
                    <span className="px-2 py-1 rounded text-xs font-medium bg-blue-50 text-blue-700">
                      {log.system}
                    </span>
                  </td>
                  <td className="py-3 px-6 text-sm">
                    <span
                      className={`px-2 py-1 rounded text-xs font-medium ${
                        log.status === 'success'
                          ? 'bg-green-50 text-green-700'
                          : log.status === 'blocked'
                          ? 'bg-yellow-50 text-yellow-700'
                          : 'bg-red-50 text-red-700'
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="py-3 px-6 text-sm text-gray-600">{formatDateTime(log.created_at)}</td>
                  <td className="py-3 px-6 text-sm text-gray-600">
                    <code className="text-xs font-mono">
                      {log.reason || JSON.stringify(log.result || {})}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {!loading && filteredLogs.length === 0 && (
          <div className="py-8 px-6 text-center text-gray-500">
            No audit records available for this filter.
          </div>
        )}
      </div>
    </div>
  )
}
