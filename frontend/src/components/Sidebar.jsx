import { Link, useLocation } from 'react-router-dom'
import { useUIStore, useAuthStore } from '@/lib/store'

const userNavigation = [
  { name: 'Dashboard', href: '/dashboard', icon: '📊' },
  { name: 'Financial', href: '/dashboard/financial', icon: '💼' },
  { name: 'Support', href: '/dashboard/support', icon: '🎫' },
  { name: 'ERP', href: '/dashboard/erp', icon: '📦' },
]

const adminNavigation = [
  { name: 'Policy', href: '/dashboard/policy', icon: '🛡️' },
  { name: 'Knowledge Base', href: '/dashboard/knowledge-base', icon: '📚' },
  { name: 'Approvals', href: '/dashboard/approvals', icon: '✅' },
  { name: 'Audit Logs', href: '/dashboard/audit', icon: '📋' },
  { name: 'Users', href: '/dashboard/users', icon: '👥' },
]

export default function Sidebar() {
  const { sidebarOpen, toggleSidebar } = useUIStore()
  const { user } = useAuthStore()
  const location = useLocation()
  const isAdmin = user?.role === 'admin'

  const navigation = isAdmin 
    ? [...userNavigation, ...adminNavigation]
    : userNavigation

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={toggleSidebar}
        className="lg:hidden fixed top-20 left-4 z-50 p-2 rounded-lg bg-gray-100 hover:bg-gray-200"
      >
        ☰
      </button>

      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 w-64 bg-gray-900 overflow-y-auto transition-opacity lg:static lg:opacity-100 ${
          sidebarOpen ? 'opacity-100' : 'opacity-0 pointer-events-none'
        }`}
        style={{ top: '64px' }}
      >
        <nav className="px-4 py-6 space-y-2">
          {navigation.map((item) => (
            <Link
              key={item.href}
              to={item.href}
              className={`flex items-center space-x-3 px-4 py-2 rounded-lg transition-colors ${
                location.pathname === item.href
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.name}</span>
            </Link>
          ))}
        </nav>
      </aside>
    </>
  )
}
