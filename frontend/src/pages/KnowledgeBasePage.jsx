import KnowledgeBaseAdmin from '@/components/KnowledgeBaseAdmin'

export default function KnowledgeBasePage() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">📚 Knowledge Base</h1>
        <p className="text-gray-600">Manage training documents and knowledge sources for the AI agent.</p>
      </div>

      <KnowledgeBaseAdmin />
    </div>
  )
}
