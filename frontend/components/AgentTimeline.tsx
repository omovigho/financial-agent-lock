'use client'

import type { AgentResponse } from '@/types'

interface TimelineEvent {
  id: string
  timestamp: string
  type: 'agent_reasoning' | 'policy_check' | 'token_request' | 'execution'
  status: 'pending' | 'success' | 'failed'
  message: string
  details?: string
}

interface AgentTimelineProps {
  events?: TimelineEvent[]
  agentResponse?: AgentResponse
}

export default function AgentTimeline({ events = [], agentResponse }: AgentTimelineProps) {
  const timelineEvents: TimelineEvent[] = events.length > 0 ? events : agentResponse ? [
    {
      id: '1',
      timestamp: new Date().toISOString(),
      type: 'agent_reasoning',
      status: 'success',
      message: agentResponse.decision || 'Agent analyzed request',
      details: agentResponse.data ? JSON.stringify(agentResponse.data) : undefined,
    },
    {
      id: '2',
      timestamp: new Date().toISOString(),
      type: 'policy_check',
      status: agentResponse.status === 'blocked' ? 'failed' : 'success',
      message: agentResponse.status === 'blocked' ? 'Policy blocked action' : 'Policy check passed',
    },
    ...(agentResponse.token ? [{
      id: '3',
      timestamp: new Date().toISOString(),
      type: 'token_request' as const,
      status: 'success' as const,
      message: 'Token granted from Vault',
      details: agentResponse.token.substring(0, 40) + '...',
    }] : []),
    {
      id: '4',
      timestamp: new Date().toISOString(),
      type: 'execution',
      status: agentResponse.status === 'success' ? 'success' : agentResponse.status === 'pending' ? 'pending' : 'failed',
      message: agentResponse.status === 'pending' ? 'Awaiting approval' : agentResponse.status === 'success' ? 'Action executed' : 'Execution failed',
    },
  ] : []

  const getEventIcon = (type: string, status: string) => {
    const statusIcon = status === 'success' ? '✓' : status === 'pending' ? '⏳' : '✗'
    
    switch (type) {
      case 'agent_reasoning':
        return '🧠'
      case 'policy_check':
        return '🛡️'
      case 'token_request':
        return '🔑'
      case 'execution':
        return '⚙️'
      default:
        return '•'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return 'text-green-700 bg-green-50 border-green-200'
      case 'failed':
        return 'text-red-700 bg-red-50 border-red-200'
      case 'pending':
        return 'text-yellow-700 bg-yellow-50 border-yellow-200'
      default:
        return 'text-gray-700 bg-gray-50 border-gray-200'
    }
  }

  if (timelineEvents.length === 0) {
    return (
      <div className="card p-6">
        <h2 className="text-xl font-bold text-gray-900 mb-4">📋 Agent Activity Timeline</h2>
        <p className="text-gray-500">Execute an action to see the activity timeline.</p>
      </div>
    )
  }

  return (
    <div className="card p-6">
      <h2 className="text-xl font-bold text-gray-900 mb-6">📋 Agent Activity Timeline</h2>

      <div className="space-y-4">
        {timelineEvents.map((event, index) => (
          <div key={event.id} className="flex gap-4">
            {/* Timeline line */}
            <div className="flex flex-col items-center">
              <div className={`w-10 h-10 rounded-full flex items-center justify-center text-lg border-2 ${getStatusColor(event.status)}`}>
                {getEventIcon(event.type, event.status)}
              </div>
              {index < timelineEvents.length - 1 && (
                <div className="w-0.5 h-12 bg-gray-300 my-2"></div>
              )}
            </div>

            {/* Event content */}
            <div className="flex-1 pt-1">
              <div className={`p-4 rounded-lg border ${getStatusColor(event.status)}`}>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-semibold capitalize">
                      {event.type.replace(/_/g, ' ')}
                    </h3>
                    <p className="text-sm mt-1">{event.message}</p>
                  </div>
                  <span className="text-xs text-gray-500 flex-shrink-0 ml-2">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                {event.details && (
                  <div className="mt-3 p-2 bg-white bg-opacity-50 rounded text-xs font-mono overflow-auto max-h-20">
                    {event.details}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
