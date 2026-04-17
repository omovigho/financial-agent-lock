'use client'

import { useState, useEffect } from 'react'
import type { InteractionStream } from '@/types'

interface InteractionStreamProps {
  filter?: 'all' | 'low' | 'medium' | 'high'
}

export default function InteractionStreamComponent({ filter = 'all' }: InteractionStreamProps) {
  const [interactions, setInteractions] = useState<InteractionStream[]>([])
  const [selectedFilter, setSelectedFilter] = useState<'all' | 'low' | 'medium' | 'high'>(filter)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // In a real app, this would fetch from the backend
    // For demo purposes, we'll show sample data
    const sampleInteractions: InteractionStream[] = [
      {
        id: '1',
        user_email: 'john@example.com',
        action: 'read_transactions',
        system: 'financial',
        risk_level: 'low',
        status: 'success',
        timestamp: new Date(Date.now() - 60000).toISOString(),
        metadata: { amount: 5000, count: 12 },
      },
      {
        id: '2',
        user_email: 'jane@example.com',
        action: 'create_refund',
        system: 'support',
        risk_level: 'medium',
        status: 'pending',
        timestamp: new Date(Date.now() - 120000).toISOString(),
        metadata: { amount: 250, reason: 'customer_request' },
      },
      {
        id: '3',
        user_email: 'bob@example.com',
        action: 'create_purchase_order',
        system: 'erp',
        risk_level: 'high',
        status: 'blocked',
        timestamp: new Date(Date.now() - 300000).toISOString(),
        metadata: { amount: 50000, vendor: 'acme_corp' },
      },
    ]
    
    setInteractions(sampleInteractions)
    setLoading(false)
  }, [])

  const filteredInteractions = selectedFilter === 'all' 
    ? interactions 
    : interactions.filter(i => i.risk_level === selectedFilter)

  const getRiskColor = (level: string) => {
    switch (level) {
      case 'low':
        return 'text-green-700 bg-green-50 border-green-200'
      case 'medium':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200'
      case 'high':
        return 'text-red-700 bg-red-50 border-red-200'
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return '✅'
      case 'pending':
        return '⏳'
      case 'blocked':
        return '🚫'
      default:
        return '•'
    }
  }

  const getRiskEmoji = (level: string) => {
    switch (level) {
      case 'low':
        return '🟢'
      case 'medium':
        return '🟡'
      case 'high':
        return '🔴'
      default:
        return '⚪'
    }
  }

  if (loading) {
    return <div className="card p-6"><p className="text-gray-500">Loading interactions...</p></div>
  }

  return (
    <div className="space-y-6">
      {/* Filter Buttons */}
      <div className="flex gap-2 flex-wrap">
        {(['all', 'low', 'medium', 'high'] as const).map((level) => (
          <button
            key={level}
            onClick={() => setSelectedFilter(level)}
            className={`px-4 py-2 rounded font-medium text-sm transition ${
              selectedFilter === level
                ? 'bg-blue-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            {level === 'all' ? '📊 All' : `${getRiskEmoji(level)} ${level.charAt(0).toUpperCase() + level.slice(1)}`}
          </button>
        ))}
      </div>

      {/* Interactions Stream */}
      {filteredInteractions.length === 0 ? (
        <div className="card p-6 text-center">
          <p className="text-gray-500">No interactions at this risk level.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredInteractions.map((interaction) => (
            <div
              key={interaction.id}
              className={`card p-4 border-2 ${getRiskColor(interaction.risk_level)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-2xl">{getStatusIcon(interaction.status)}</span>
                    <div>
                      <h3 className="font-semibold">
                        {interaction.action.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}
                      </h3>
                      <p className="text-sm">{interaction.user_email}</p>
                    </div>
                  </div>
                </div>

                <div className="text-right flex-shrink-0">
                  <div className="font-medium text-lg">{getRiskEmoji(interaction.risk_level)}</div>
                  <div className="text-xs font-medium uppercase tracking-wide">
                    {interaction.risk_level} Risk
                  </div>
                </div>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                <div>
                  <p className="text-xs opacity-70">System</p>
                  <p className="font-medium">{interaction.system.toUpperCase()}</p>
                </div>
                <div>
                  <p className="text-xs opacity-70">Status</p>
                  <p className="font-medium">{interaction.status.charAt(0).toUpperCase() + interaction.status.slice(1)}</p>
                </div>
                <div>
                  <p className="text-xs opacity-70">Time</p>
                  <p className="font-medium">{new Date(interaction.timestamp).toLocaleTimeString()}</p>
                </div>
              </div>

              {Object.keys(interaction.metadata).length > 0 && (
                <div className="mt-3 p-2 bg-white bg-opacity-50 rounded text-xs">
                  <p className="opacity-70">Details: {JSON.stringify(interaction.metadata)}</p>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
