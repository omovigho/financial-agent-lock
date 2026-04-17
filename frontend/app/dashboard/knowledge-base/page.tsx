'use client'

import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import KnowledgeBaseAdmin from '@/components/KnowledgeBaseAdmin'

export default function KnowledgeBasePage() {
  const { user } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    // Redirect if not admin
    if (user && user.role !== 'admin') {
      router.push('/dashboard')
    }
  }, [user, router])

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
      <h1 className="text-3xl font-bold text-gray-900 mb-8">📚 Knowledge Base Management</h1>
      <KnowledgeBaseAdmin />
    </div>
  )
}
