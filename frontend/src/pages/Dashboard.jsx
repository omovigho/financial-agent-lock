import AgentPanel from '@/components/AgentPanel'
import InteractionStream from '@/components/InteractionStream'
import ApprovalQueue from '@/components/ApprovalQueue'

export default function Dashboard() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">📊 Dashboard</h1>
        <p className="text-gray-600">Welcome to Agent-Lock. Manage your AI agent operations securely.</p>
      </div>

      <AgentPanel />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <InteractionStream />
        <ApprovalQueue />
      </div>
    </div>
  )
}
