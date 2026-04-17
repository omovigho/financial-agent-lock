'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import { policyAPI } from '@/lib/api'

interface PolicyExample {
  system: string
  action: string
  rule: string
  description: string
  threshold?: number
}

export default function PolicyPage() {
  const { user } = useAuthStore()
  const router = useRouter()
  const [policies, setPolicies] = useState<PolicyExample[]>([])
  const [selectedSystem, setSelectedSystem] = useState<string | null>(null)

  useEffect(() => {
    // Redirect if not admin
    if (user && user.role !== 'admin') {
      router.push('/dashboard')
    } else {
      loadPolicies()
    }
  }, [user, router])

  const loadPolicies = async () => {
    try {
      const res = await policyAPI.demo()
      setPolicies(res.data.examples)
    } catch (error) {
      console.error('Failed to load policies:', error)
    }
  }

  const systems = ['financial', 'support', 'erp']

  const filteredPolicies = selectedSystem
    ? policies.filter((p) => p.system === selectedSystem)
    : policies

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
      <h1 className="text-3xl font-bold text-gray-900 mb-8">🛡️ Policy Engine Dashboard</h1>

      {/* Policy Overview */}
      <div className="card p-6 mb-8">
        <h2 className="text-2xl font-bold text-gray-900 mb-4">Security Policies</h2>
        <p className="text-gray-600">
          The policy engine controls all agent actions by enforcing security rules. Each action is
          evaluated against policies before execution.
        </p>
      </div>

      {/* System Filters */}
      <div className="mb-6 flex flex-wrap gap-2">
        <button
          onClick={() => setSelectedSystem(null)}
          className={`btn ${selectedSystem === null ? 'btn-primary' : 'btn-outline'}`}
        >
          All Systems
        </button>
        {systems.map((system) => (
          <button
            key={system}
            onClick={() => setSelectedSystem(system)}
            className={`btn ${selectedSystem === system ? 'btn-primary' : 'btn-outline'}`}
          >
            {system.charAt(0).toUpperCase() + system.slice(1)}
          </button>
        ))}
      </div>

      {/* Policy Details */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {filteredPolicies.map((policy, idx) => (
          <div key={idx} className="card p-6">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">{policy.action}</h3>
                <p className="text-sm text-gray-600 mt-1">{policy.system}</p>
              </div>
              <span
                className={`badge ${
                  policy.rule === 'allow'
                    ? 'badge-success'
                    : 'badge-warning'
                }`}
              >
                {policy.rule}
              </span>
            </div>

            <p className="text-gray-700 mb-4">{policy.description}</p>

            {policy.threshold && (
              <div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
                <p className="text-sm text-blue-900">
                  <strong>Threshold:</strong> ${policy.threshold.toLocaleString()}
                </p>
              </div>
            )}

            <div className="mt-4 p-3 bg-gray-50 rounded-lg">
              <p className="text-xs text-gray-600">
                <strong>How it works:</strong>
              </p>
              <p className="text-xs text-gray-600 mt-2">
                {policy.rule === 'allow'
                  ? `Users can ${policy.action} without restrictions`
                  : `Users must request approval for ${policy.action} actions`}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Policy Flow Explanation */}
      <div className="mt-8 card p-6 bg-blue-50 border-blue-200">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">🔄 Policy Evaluation Flow</h3>
        <div className="space-y-2 text-sm text-gray-700">
          <p>1. <strong>Agent Request:</strong> Agent requests to perform an action</p>
          <p>2. <strong>Policy Check:</strong> Policy engine evaluates the request against rules</p>
          <p>3. <strong>Decision:</strong> Allow, Deny, or Require Approval</p>
          <p>4. <strong>Token Request:</strong> If allowed, Token Vault creates scoped token</p>
          <p>5. <strong>Execution:</strong> Agent executes action with token</p>
          <p>6. <strong>Audit Log:</strong> Action is recorded in audit trail</p>
        </div>
      </div>
    </div>
  )
}
