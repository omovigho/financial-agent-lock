import { useEffect, useState } from 'react'
import { knowledgeBaseAPI } from '@/lib/api'

export default function KnowledgeBaseAdmin() {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [selectedFile, setSelectedFile] = useState(null)
  const [deletingId, setDeletingId] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (message, type = 'success') => {
    setToast({ message, type })
  }

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    loadDocuments()
  }, [])

  const loadDocuments = async () => {
    try {
      const res = await knowledgeBaseAPI.listDocuments('active')
      const data = res.data
      setDocuments(Array.isArray(data) ? data : data.documents || [])
    } catch (error) {
      console.error('Failed to load documents:', error)
      showToast('Failed to load documents', 'error')
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = (e) => {
    setSelectedFile(e.target.files?.[0] || null)
  }

  const handleUpload = async () => {
    if (!selectedFile) return

    setUploading(true)
    try {
      const filename = selectedFile.name
      const formData = new FormData()
      formData.append('file', selectedFile)
      
      await knowledgeBaseAPI.uploadDocument(formData)
      await loadDocuments()
      setSelectedFile(null)
      showToast(`"${filename}" is successfully uploaded`)
    } catch (error) {
      console.error('Upload failed:', error)
      showToast('Upload failed', 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (doc) => {
    if (!window.confirm(`Delete "${doc.filename}"? This cannot be undone.`)) return

    setDeletingId(doc.doc_id)
    try {
      await knowledgeBaseAPI.deleteDocument(doc.doc_id, { doc_id: doc.doc_id, filename: doc.filename })
      await loadDocuments()
      showToast(`"${doc.filename}" is successfully deleted`)
    } catch (error) {
      console.error('Delete failed:', error)
      showToast('Delete failed', 'error')
    } finally {
      setDeletingId(null)
    }
  }

  const formatDateTime = (value) => {
    if (!value) return 'N/A'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return 'N/A'
    return date.toLocaleString()
  }

  return (
    <div className="space-y-6">
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg ${{
            success: 'bg-green-600',
            error: 'bg-red-600',
          }[toast.type] || 'bg-gray-800'}`}
        >
          {toast.message}
        </div>
      )}

      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">📚 Upload Documents</h2>
        
        <div className="space-y-4">
          <div>
            <label className="label">Select Document</label>
            <input
              type="file"
              onChange={handleFileSelect}
              accept=".pdf,.doc,.docx,.txt"
              className="w-full"
            />
          </div>
          
          <button
            onClick={handleUpload}
            disabled={!selectedFile || uploading}
            className="btn-primary w-full disabled:opacity-50"
          >
            {uploading ? 'Uploading...' : '⬆️ Upload'}
          </button>
        </div>
      </div>

      <div className="card p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">📋 Documents</h2>
        
        <div className="space-y-3">
          {loading ? (
            <p className="text-gray-500 text-center py-4">Loading documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-gray-500 text-center py-4">No documents uploaded yet</p>
          ) : (
            documents.map(doc => (
              <div key={doc.id} className="border border-gray-200 rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="font-semibold text-gray-900">{doc.filename}</p>
                  <p className="text-sm text-gray-600">Uploaded by: {doc.uploaded_by ?? 'N/A'}</p>
                  <p className="text-sm text-gray-600">Created at: {formatDateTime(doc.created_at)}</p>
                </div>
                <button
                  onClick={() => handleDelete(doc)}
                  disabled={deletingId === doc.doc_id}
                  className="text-red-600 hover:text-red-700 disabled:opacity-50"
                >
                  {deletingId === doc.doc_id ? '⏳' : '🗑️'}
                </button>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
