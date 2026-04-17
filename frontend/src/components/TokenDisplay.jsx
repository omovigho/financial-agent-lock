import { useState } from 'react'
import { useAuthStore } from '@/lib/store'

export default function TokenDisplay() {
  const { token } = useAuthStore()
  const [copySuccess, setCopySuccess] = useState(false)

  const handleCopy = () => {
    if (token) {
      navigator.clipboard.writeText(token)
      setCopySuccess(true)
      setTimeout(() => setCopySuccess(false), 2000)
    }
  }

  if (!token) {
    return (
      <div className="card p-4 text-center text-gray-500">
        <p>No active token</p>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-900">Access Token</h3>
        <button
          onClick={handleCopy}
          className="text-sm text-blue-600 hover:text-blue-700"
        >
          {copySuccess ? '✅ Copied!' : '📋 Copy'}
        </button>
      </div>
      <code className="text-xs bg-gray-100 p-2 rounded block overflow-x-auto truncate">
        {token.substring(0, 20)}...{token.substring(token.length - 20)}
      </code>
    </div>
  )
}
