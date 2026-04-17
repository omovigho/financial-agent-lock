import { useState, useEffect } from 'react'

export default function InteractionStream({ filter = 'all' }) {
  const [interactions, setInteractions] = useState([])
  const [selectedFilter, setSelectedFilter] = useState(filter)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Sample data
    const sampleInteractions = [
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

  const getRiskColor = (level) => {
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

  const getStatusIcon = (status) => {
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

  const getRiskEmoji = (level) => {
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
    <div className="card p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold text-gray-900">📊 Real-Time Activity Stream</h2>
        
        <div className="flex gap-2">
          {['all', 'low', 'medium', 'high'].map((level) => (
            <button
              key={level}
              onClick={() => setSelectedFilter(level)}
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedFilter === level
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {level === 'all' ? 'All' : level.charAt(0).toUpperCase() + level.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3 max-h-96 overflow-y-auto">
        {filteredInteractions.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No interactions found</p>
        ) : (
          filteredInteractions.map((interaction) => (
            <div
              key={interaction.id}
              className={`border rounded-lg p-4 ${getRiskColor(interaction.risk_level)}`}
            >
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">{getStatusIcon(interaction.status)}</span>
                    <span className="font-semibold">{interaction.action}</span>
                    <span className="text-xs px-2 py-1 rounded bg-gray-200 text-gray-700">
                      {interaction.system}
                    </span>
                  </div>
                  <p className="text-sm mb-1">{interaction.user_email}</p>
                  <p className="text-xs opacity-75">{new Date(interaction.timestamp).toLocaleString()}</p>
                </div>
                <span className="text-2xl">{getRiskEmoji(interaction.risk_level)}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}
