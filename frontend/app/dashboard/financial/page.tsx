'use client'

import { useState, useEffect } from 'react'
import AgentPanel from '@/components/AgentPanel'
import { agentAPI } from '@/lib/api'
import type { Transaction } from '@/types'
import { formatCurrency } from '@/lib/utils'

export default function FinancialPage() {
  const [transactions, setTransactions] = useState<Transaction[]>([])
  const [balance, setBalance] = useState(0)

  const loadFinancialData = async () => {
    try {
      // This would be loaded from agent execution
    } catch (error) {
      console.error('Failed to load financial data:', error)
    }
  }

  useEffect(() => {
    loadFinancialData()
  }, [])

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-8">💼 Financial Analysis</h1>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Agent Panel */}
        <div className="lg:col-span-2">
          <AgentPanel onActionExecuted={loadFinancialData} />
        </div>

        {/* Quick Stats */}
        <div className="space-y-6">
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Account Balance</h3>
            <p className="text-3xl font-bold text-green-600">
              {formatCurrency(balance)}
            </p>
            <p className="text-sm text-gray-600 mt-2">Current balance</p>
          </div>

          <div className="card p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Available Actions</h3>
            <ul className="space-y-2 text-sm text-gray-600">
              <li>✓ Read transactions</li>
              <li>✓ Check balance</li>
              <li>⚠ Create transaction (requires approval)</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      {transactions.length > 0 && (
        <div className="mt-8 card p-6">
          <h2 className="text-xl font-bold text-gray-900 mb-4">Recent Transactions</h2>
          <div className="space-y-2">
            {transactions.map((tx) => (
              <div
                key={tx.id}
                className="flex justify-between items-center p-3 bg-gray-50 rounded-lg"
              >
                <div>
                  <p className="font-medium text-gray-900">{tx.description}</p>
                  <p className="text-sm text-gray-600">{tx.category}</p>
                </div>
                <div className="text-right">
                  <p className={`font-semibold ${tx.amount > 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {formatCurrency(tx.amount)}
                  </p>
                  <p className="text-xs text-gray-500">{tx.date}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
