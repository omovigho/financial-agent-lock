'use client'

import { useState, useEffect } from 'react'
import { useAuthStore } from '@/lib/store'
import { useRouter } from 'next/navigation'
import type { User } from '@/types'

interface UserWithRole extends User {
  is_active: boolean
  created_at: string
}

export default function UsersPage() {
  const { user, token } = useAuthStore()
  const router = useRouter()
  const [users, setUsers] = useState<UserWithRole[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedUser, setSelectedUser] = useState<UserWithRole | null>(null)
  const [showRoleModal, setShowRoleModal] = useState(false)
  const [newRole, setNewRole] = useState<string>('user')
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    // Redirect if not admin
    if (user && user.role !== 'admin') {
      router.push('/dashboard')
    } else {
      loadUsers()
    }
  }, [user, router])

  const loadUsers = async () => {
    try {
      const response = await fetch('/api/auth/users', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      })
      if (response.ok) {
        const data = await response.json()
        setUsers(data.users || [])
      } else {
        console.error('Failed to load users')
      }
    } catch (error) {
      console.error('Error loading users:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleRoleChange = (selectedUser: UserWithRole) => {
    setSelectedUser(selectedUser)
    setNewRole(selectedUser.role)
    setShowRoleModal(true)
  }

  const handleSaveRole = async () => {
    if (!selectedUser) return

    setUpdating(true)
    try {
      const response = await fetch(`/api/auth/users/${selectedUser.id}/role`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          user_id: selectedUser.id,
          role: newRole,
        }),
      })

      if (response.ok) {
        // Update local state
        setUsers(users.map(u => 
          u.id === selectedUser.id 
            ? { ...u, role: newRole }
            : u
        ))
        setShowRoleModal(false)
        setSelectedUser(null)
      } else {
        alert('Failed to update role')
      }
    } catch (error) {
      console.error('Error updating role:', error)
      alert('Error updating role')
    } finally {
      setUpdating(false)
    }
  }

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
      <h1 className="text-3xl font-bold text-gray-900 mb-8">👥 User Management</h1>

      {loading ? (
        <div className="card p-6 text-center">
          <p className="text-gray-600">Loading users...</p>
        </div>
      ) : (
        <div className="card p-6">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Name</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Email</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Role</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Status</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Created</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-900">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-4 text-gray-900">{u.name}</td>
                    <td className="py-3 px-4 text-gray-600">{u.email}</td>
                    <td className="py-3 px-4">
                      <span className={`badge ${u.role === 'admin' ? 'bg-red-100 text-red-800' : 'bg-blue-100 text-blue-800'}`}>
                        {u.role}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`badge ${u.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-gray-600">
                      {new Date(u.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-3 px-4">
                      <button
                        onClick={() => handleRoleChange(u)}
                        className="btn btn-sm btn-ghost"
                      >
                        Change Role
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Role Change Modal */}
      {showRoleModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="card p-6 max-w-md w-full mx-4">
            <h2 className="text-2xl font-bold text-gray-900 mb-4">Change User Role</h2>
            <div className="mb-6">
              <p className="text-gray-600 mb-2">User: <span className="font-semibold">{selectedUser.name}</span></p>
              <p className="text-gray-600 mb-2">Email: <span className="font-semibold">{selectedUser.email}</span></p>
              <div className="mt-4">
                <label className="block text-sm font-medium text-gray-700 mb-2">New Role</label>
                <select
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:border-blue-500"
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <div className="flex gap-3">
              <button
                onClick={() => setShowRoleModal(false)}
                className="flex-1 btn btn-outline"
                disabled={updating}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRole}
                className="flex-1 btn btn-primary"
                disabled={updating || newRole === selectedUser.role}
              >
                {updating ? 'Updating...' : 'Update Role'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
