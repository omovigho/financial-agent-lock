'use client'

import { useState, useEffect, type FormEvent } from 'react'
import { knowledgeBaseAPI } from '@/lib/api'

interface Document {
  id: number
  doc_id: string
  filename: string
  uploaded_by?: number | null
  file_extension: string
  file_size_bytes: number
  status: 'active' | 'archived' | 'deleted'
  created_at: string
}

interface ToastState {
  message: string
  type: 'success' | 'error'
}

export default function KnowledgeBaseAdmin() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [stats, setStats] = useState<any>(null)
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [toast, setToast] = useState<ToastState | null>(null)

  const showToast = (message: string, type: ToastState['type'] = 'success') => {
    setToast({ message, type })
  }

  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setToast(null), 2200)
    return () => clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    initializePage()
  }, [])

  const initializePage = async () => {
    await loadDocuments()
    await loadStats()
  }

  const loadDocuments = async () => {
    try {
      const res = await knowledgeBaseAPI.listDocuments('active')
      const data = res.data
      setDocuments(Array.isArray(data) ? data : data.documents || [])
    } catch (error) {
      console.error('Failed to load documents:', error)
      showToast('Failed to load documents', 'error')
    }
  }

  const loadStats = async () => {
    try {
      const res = await knowledgeBaseAPI.getStats()
      setStats(res.data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpload = async (e: FormEvent) => {
    e.preventDefault()
    if (!selectedFile) return

    setUploading(true)
    try {
      const filename = selectedFile.name
      const formData = new FormData()
      formData.append('file', selectedFile)
      
      await knowledgeBaseAPI.uploadDocument(formData)
      setSelectedFile(null)
      
      await loadDocuments()
      await loadStats()
      showToast(`"${filename}" is successfully uploaded`)
    } catch (error) {
      showToast('Upload failed: ' + (error instanceof Error ? error.message : 'Unknown error'), 'error')
    } finally {
      setUploading(false)
    }
  }

  const handleDelete = async (docId: string, filename: string) => {
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return

    setDeletingId(docId)
    try {
      await knowledgeBaseAPI.deleteDocument(docId, { doc_id: docId, filename })
      
      await loadDocuments()
      await loadStats()
      showToast(`"${filename}" is successfully deleted`)
    } catch (error) {
      showToast('Delete failed: ' + (error instanceof Error ? error.message : 'Unknown error'), 'error')
    } finally {
      setDeletingId(null)
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 B'
    const k = 1024
    const sizes = ['B', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 10) / 10 + ' ' + sizes[i]
  }

  return (
    <div className="space-y-6">
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 rounded-lg px-4 py-2 text-sm font-medium text-white shadow-lg ${
            toast.type === 'error' ? 'bg-red-600' : 'bg-green-600'
          }`}
        >
          {toast.message}
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <div className="grid grid-cols-3 gap-4">
          <div className="card p-4 text-center">
            <p className="text-3xl font-bold text-blue-600">{stats.total_documents}</p>
            <p className="text-sm text-gray-600">Total Documents</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-3xl font-bold text-green-600">{stats.active_documents}</p>
            <p className="text-sm text-gray-600">Active Documents</p>
          </div>
          <div className="card p-4 text-center">
            <p className="text-2xl font-bold text-purple-600">{stats.total_size_mb}MB</p>
            <p className="text-sm text-gray-600">Total Size</p>
          </div>
        </div>
      )}

      {/* Upload Form */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">📤 Upload Document</h3>
        <form onSubmit={handleUpload} className="space-y-4">
          <div className="border-2 border-dashed border-gray-300 rounded-lg p-6">
            <input
              type="file"
              accept=".pdf,.docx,.txt,.doc,.pptx,.xlsx,.csv,.html,.json,.md"
              onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
              disabled={uploading}
              className="w-full"
            />
            <p className="text-xs text-gray-500 mt-2">
              Supported: PDF, DOCX, TXT, DOC, XLSX, CSV, JSON, MD (Max 25MB)
            </p>
          </div>
          <button
            type="submit"
            disabled={!selectedFile || uploading}
            className="w-full btn-primary disabled:opacity-50"
          >
            {uploading ? '⏳ Uploading...' : '📤 Upload Document'}
          </button>
        </form>
      </div>

      {/* Documents List */}
      <div className="card p-6">
        <h3 className="text-lg font-bold text-gray-900 mb-4">📚 Documents in Knowledge Base</h3>
        
        {documents.length === 0 ? (
          <p className="text-gray-500">No documents uploaded yet.</p>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between p-3 border border-gray-200 rounded-lg hover:bg-gray-50">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📄</span>
                    <div>
                      <p className="font-medium text-gray-900">{doc.filename}</p>
                      <p className="text-xs text-gray-500">
                        {formatFileSize(doc.file_size_bytes)} • Uploaded by {doc.uploaded_by ?? 'N/A'} • Added {new Date(doc.created_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(doc.doc_id, doc.filename)}
                  disabled={deletingId === doc.doc_id}
                  className="px-3 py-1 text-sm text-red-600 hover:bg-red-50 rounded disabled:opacity-50"
                >
                  {deletingId === doc.doc_id ? '⏳' : '🗑️'} Delete
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
