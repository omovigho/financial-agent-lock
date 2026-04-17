import { useEffect, useState } from 'react'
import { authAPI } from '@/lib/api'

export default function UsersPage() {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [selectedUser, setSelectedUser] = useState(null)
  const [newRole, setNewRole] = useState('user')
  const [updating, setUpdating] = useState(false)

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    setLoading(true)
    setError('')
    try {
      const response = await authAPI.listUsers()
      setUsers(response?.data?.users || [])
    } catch (err) {
      console.error('Failed to load users:', err)
      setError('Failed to load users.')
      setUsers([])
    } finally {
      setLoading(false)
    }
  }

  const handleRoleChange = (user) => {
    setSelectedUser(user)
    setNewRole(user.role)
  }

  const handleSaveRole = async () => {
    if (!selectedUser || selectedUser.role === newRole) {
      setSelectedUser(null)
      return
    }

    setUpdating(true)
    try {
      await authAPI.updateUserRole(selectedUser.id, newRole)
      setUsers((prevUsers) =>
        prevUsers.map((u) => (u.id === selectedUser.id ? { ...u, role: newRole } : u))
      )
      setSelectedUser(null)
    } catch (err) {
      console.error('Failed to update role:', err)
      setError('Failed to update user role.')
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-4xl font-bold text-gray-900 mb-2">👥 User Management</h1>
        <p className="text-gray-600">All registered users and their access roles.</p>
      </div>

      <div className="card p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Users ({users.length})</h2>
          <button onClick={loadUsers} className="btn-secondary" disabled={loading}>
            Refresh
          </button>
        </div>

        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-8 text-center text-gray-500">Loading users...</div>
        ) : users.length === 0 ? (
          <div className="py-8 text-center text-gray-500">No users found.</div>
        ) : (
          <div className="space-y-3">
            {users.map((user) => (
              <div key={user.id} className="border border-gray-200 rounded-lg p-4 flex items-center justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <h3 className="font-semibold text-gray-900 truncate">{user.name}</h3>
                  <p className="text-sm text-gray-600 truncate">{user.email}</p>
                  <p className="text-xs text-gray-500 mt-1">
                    Created: {new Date(user.created_at).toLocaleDateString()}
                  </p>
                </div>
                <select
                  value={user.role}
                  onChange={(e) => {
                    handleRoleChange(user)
                    setNewRole(e.target.value)
                  }}
                  className="input text-sm"
                  disabled={updating && selectedUser?.id === user.id}
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            ))}
          </div>
        )}

        {selectedUser && (
          <div className="mt-6 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-blue-900">
              Update role for <span className="font-semibold">{selectedUser.email}</span> to <span className="font-semibold">{newRole}</span>?
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setSelectedUser(null)}
                className="btn-secondary"
                disabled={updating}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveRole}
                className="btn-primary"
                disabled={updating || selectedUser.role === newRole}
              >
                {updating ? 'Saving...' : 'Save Role'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
