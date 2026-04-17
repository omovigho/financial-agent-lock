'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import { formatDate } from '@/lib/utils'

interface AuditLog {
  id: number
  user_id: number
  action: string
  system: string
  resource: string
  method: string
  status: 'success' | 'failure' | 'blocked'
  reason?: string
  created_at: string
}

export default function AuditPage() {
  const { user } = useAuthStore()
  const router = useRouter()
  const [logs, setLogs] = useState<AuditLog[]>([])
  const [filterSystem, setFilterSystem] = useState<string | null>(null)
  const [filterStatus, setFilterStatus] = useState<string | null>(null)

  useEffect(() => {
    // Redirect if not admin
    if (user && user.role !== 'admin') {
      router.push('/dashboard')
    } else {
      loadLogs()
    }
  }, [filterSystem, filterStatus, user, router])

  const loadLogs = async () => {
    try {
      // Mock audit logs for demo
      setLogs([
        {
          id: 1,
          user_id: user?.id || 0,
          action: 'read_transactions',
          system: 'financial',
          resource: 'transactions',
          method: 'GET',
          status: 'success',
          created_at: new Date(Date.now() - 3600000).toISOString(),
        },
        {
          id: 2,
          user_id: user?.id || 0,
          action: 'create_transaction',
          system: 'financial',
          resource: 'transactions',
          method: 'POST',
          status: 'blocked',
          reason: 'Requires approval for amounts > $1000',
          created_at: new Date(Date.now() - 1800000).toISOString(),
        },
        {
          id: 3,
          user_id: user?.id || 0,
          action: 'process_refund',
          system: 'support',
          resource: 'tickets',
          method: 'POST',
          status: 'success',
          created_at: new Date(Date.now() - 900000).toISOString(),
        },
      ])
    } catch (error) {
      console.error('Failed to load logs:', error)
    }
  }

  const filteredLogs = logs.filter((log) => {
    if (filterSystem && log.system !== filterSystem) return false
    if (filterStatus && log.status !== filterStatus) return false
    return true
  })

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

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">📋 Audit Log</h1>

      {/* Info Card */}
      <div className="card p-6 mb-8 bg-blue-50 border-blue-200">
        <h3 className="font-semibold text-gray-900 mb-2">Audit Trail</h3>
        <p className="text-sm text-gray-700">
          Complete record of all agent actions, policy decisions, and system operations. Used for
          security compliance and debugging.
        </p>
      </div>

      {/* Filters */}
      <div className="mb-6 space-y-4">
        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">System</label>
          <select
            value={filterSystem || ''}
            onChange={(e) => setFilterSystem(e.target.value || null)}
            className="w-full md:w-48 px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Systems</option>
            <option value="financial">Financial</option>
            <option value="support">Support</option>
            <option value="erp">ERP</option>
          </select>
        </div>

        <div>
          <label className="text-sm font-medium text-gray-700 block mb-2">Status</label>
          <select
            value={filterStatus || ''}
            onChange={(e) => setFilterStatus(e.target.value || null)}
            className="w-full md:w-48 px-4 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Statuses</option>
            <option value="success">Success</option>
            <option value="blocked">Blocked</option>
            <option value="failure">Failure</option>
          </select>
        </div>
      </div>

      {/* Logs Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  Timestamp
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  Action
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  System
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  Method
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-sm font-semibold text-gray-900">
                  Details
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.map((log) => (
                <tr key={log.id} className="border-b border-gray-200 hover:bg-gray-50">
                  <td className="px-6 py-3 text-sm text-gray-900">
                    {formatDate(log.created_at)}
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-900">{log.action}</td>
                  <td className="px-6 py-3 text-sm text-gray-600">{log.system}</td>
                  <td className="px-6 py-3 text-sm">
                    <span className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-xs font-medium">
                      {log.method}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm">
                    <span
                      className={`badge ${
                        log.status === 'success'
                          ? 'badge-success'
                          : log.status === 'blocked'
                          ? 'badge-warning'
                          : 'badge-danger'
                      }`}
                    >
                      {log.status}
                    </span>
                  </td>
                  <td className="px-6 py-3 text-sm text-gray-600">
                    {log.reason ? (
                      <span title={log.reason} className="cursor-help">
                        ℹ️
                      </span>
                    ) : (
                      '-'
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filteredLogs.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No audit logs match the selected filters
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <span className="badge badge-success">Success</span>
          <p className="text-sm text-gray-600 mt-2">Action executed successfully</p>
        </div>
        <div className="card p-4">
          <span className="badge badge-warning">Blocked</span>
          <p className="text-sm text-gray-600 mt-2">Action blocked by policy</p>
        </div>
        <div className="card p-4">
          <span className="badge badge-danger">Failure</span>
          <p className="text-sm text-gray-600 mt-2">Action failed during execution</p>
        </div>
      </div>
    </div>
  )
}
