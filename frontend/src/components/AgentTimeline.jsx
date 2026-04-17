import { useEffect } from 'react'

export default function AgentTimeline({ events = [] }) {
  return (
    <div className="card p-6">
      <h2 className="text-2xl font-bold text-gray-900 mb-6">⏱️ Execution Timeline</h2>
      
      <div className="space-y-4">
        {events.length === 0 ? (
          <p className="text-gray-500 text-center py-4">No events recorded</p>
        ) : (
          <div className="relative">
            {events.map((event, idx) => (
              <div key={idx} className="flex gap-4">
                <div className="flex flex-col items-center">
                  <div className="w-3 h-3 bg-blue-600 rounded-full" />
                  {idx < events.length - 1 && (
                    <div className="w-1 bg-gray-200 flex-1 my-2" style={{ height: '60px' }} />
                  )}
                </div>
                <div className="pb-8">
                  <p className="font-semibold text-gray-900">{event.step}</p>
                  <p className="text-sm text-gray-600">{event.description}</p>
                  <p className="text-xs text-gray-500 mt-1">{event.timestamp}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
