'use client'

import { useEffect, useState } from 'react'
import { agentAPI } from '@/lib/api'
import type { Token } from '@/types'
import { formatDate } from '@/lib/utils'

export default function TokenDisplay() {
  const [tokens, setTokens] = useState<Token[]>([])
  const [loading, setLoading] = useState(true)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  useEffect(() => {
    loadTokens()
  }, [])

  const loadTokens = async () => {
    try {
      const res = await agentAPI.listTokens()
      setTokens(res.data.tokens)
    } catch (error) {
      console.error('Failed to load tokens:', error)
    } finally {
      setLoading(false)
    }
  }

  const getTokenStatusColor = (expiresAt: string) => {
    const timeUntilExpiry = new Date(expiresAt).getTime() - Date.now()
    const hoursRemaining = timeUntilExpiry / 3600000

    if (hoursRemaining < 1) return 'text-red-700 bg-red-50 border-red-200'
    if (hoursRemaining < 24) return 'text-yellow-700 bg-yellow-50 border-yellow-200'
    return 'text-green-700 bg-green-50 border-green-200'
  }

  const getTokenStatusLabel = (expiresAt: string) => {
    const timeUntilExpiry = new Date(expiresAt).getTime() - Date.now()
    const hoursRemaining = timeUntilExpiry / 3600000

    if (hoursRemaining < 1) return '⚠️ Expiring Soon'
    if (hoursRemaining < 24) return '⏰ Expiring Today'
    return '✅ Active'
  }

  const maskTokenValue = (token: string) => {
    if (token.length <= 8) return token
    return token.substring(0, 4) + '••••••••' + token.substring(token.length - 4)
  }

  if (loading) {
    return <div className="text-gray-500">Loading tokens...</div>
  }

  return (
    <div className="card p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">🔐 Active Tokens</h3>
        <span className="text-xs bg-blue-100 text-blue-800 px-2.5 py-0.5 rounded-full">
          {tokens.length} {tokens.length === 1 ? 'token' : 'tokens'}
        </span>
      </div>

      {tokens.length === 0 ? (
        <div className="card p-4 text-center bg-gray-50">
          <p className="text-gray-500">No active tokens</p>
          <p className="text-xs text-gray-400 mt-2">Tokens are managed by Token Vault</p>
        </div>
      ) : (
        <div className="space-y-2">
          {tokens.map((token) => {
            const isExpanded = expandedId === token.token_id
            const statusColor = getTokenStatusColor(token.expires_at)

            return (
              <div key={token.token_id}>
                <button
                  onClick={() => setExpandedId(isExpanded ? null : token.token_id)}
                  className={`w-full p-4 rounded-lg border-2 transition text-left hover:shadow-md ${statusColor}`}
                >
                  {/* Header Row */}
                  <div className="flex justify-between items-start gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <span className="font-mono font-bold">{token.system}</span>
                        <span className="text-xs px-2 py-1 bg-white bg-opacity-50 rounded">
                          {token.scope}
                        </span>
                      </div>
                      <p className="text-xs opacity-70">
                        Source: Token Vault • ID: {token.token_id.substring(0, 12)}...
                      </p>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <div className="text-xs font-bold uppercase tracking-wide whitespace-nowrap">
                        {getTokenStatusLabel(token.expires_at)}
                      </div>
                      <span className="text-xl">{isExpanded ? '▼' : '▶'}</span>
                    </div>
                  </div>

                  {/* Expiry Bar */}
                  <div className="mt-2 text-xs opacity-70">
                    Expires {formatDate(token.expires_at)}
                  </div>
                </button>

                {/* Expanded Details */}
                {isExpanded && (
                  <div className="p-4 bg-white bg-opacity-50 border-x-2 border-b-2 border-gray-200 space-y-3">
                    {/* Token Metadata Grid */}
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <p className="text-xs font-medium opacity-75">System</p>
                        <p className="font-bold">{token.system.toUpperCase()}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium opacity-75">Scope</p>
                        <p className="font-bold">{token.scope}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium opacity-75">Created</p>
                        <p className="text-sm">{formatDate(token.created_at)}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium opacity-75">Expires</p>
                        <p className="text-sm">{formatDate(token.expires_at)}</p>
                      </div>
                    </div>

                    {/* Token ID */}
                    <div>
                      <p className="text-xs font-medium opacity-75">Token ID</p>
                      <p className="font-mono text-sm bg-black bg-opacity-5 p-2 rounded">
                        {token.token_id}
                      </p>
                    </div>

                    {/* Vault Source */}
                    <div className="bg-blue-50 border border-blue-200 rounded p-3">
                      <p className="text-xs font-medium text-blue-900 mb-1">🔐 Vault Information</p>
                      <div className="space-y-1 text-xs text-blue-800">
                        <p><strong>Source:</strong> Token Vault</p>
                        <p><strong>Status:</strong> Encrypted & Secure</p>
                        <p><strong>Raw Value:</strong> Not Displayed (Security Policy)</p>
                        <p className="text-blue-700 font-medium mt-2">⚠️ Token never exposed in UI or logs</p>
                      </div>
                    </div>

                    {/* Permissions */}
                    {token.permissions && token.permissions.length > 0 && (
                      <div>
                        <p className="text-xs font-medium opacity-75 mb-2">Permissions</p>
                        <div className="flex flex-wrap gap-2">
                          {token.permissions.map((perm) => (
                            <span
                              key={perm}
                              className="text-xs px-2 py-1 bg-gray-200 rounded"
                            >
                              {perm}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* Security Note */}
      <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded">
        <p className="text-xs text-amber-900">
          <strong>🔒 Security:</strong> All tokens are stored securely in Token Vault. The agent accesses tokens through the backend only. Raw token values are never displayed or logged.
        </p>
      </div>
    </div>
  )
}
