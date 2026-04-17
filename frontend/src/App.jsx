import { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { useAuthStore } from '@/lib/store'
import { authAPI } from '@/lib/api'

import Navbar from '@/components/Navbar'
import Sidebar from '@/components/Sidebar'
import LoginPage from '@/pages/LoginPage'
import WelcomePage from '@/pages/WelcomePage'
import Dashboard from '@/pages/Dashboard'
import FinancialPage from '@/pages/FinancialPage'
import SupportPage from '@/pages/SupportPage'
import ErpPage from '@/pages/ErpPage'
import PolicyPage from '@/pages/PolicyPage'
import KnowledgeBasePage from '@/pages/KnowledgeBasePage'
import ApprovalsPage from '@/pages/ApprovalsPage'
import AuditPage from '@/pages/AuditPage'
import UsersPage from '@/pages/UsersPage'

function ProtectedLayout({ children }) {
  return (
    <>
      <Navbar />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 ml-0 lg:ml-64 pt-20">{children}</main>
      </div>
    </>
  )
}

function ProtectedRoute({ children }) {
  const { isAuthenticated, setUser, setToken } = useAuthStore()
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Try to restore user from localStorage
    const token = localStorage.getItem('access_token')
    if (token && !isAuthenticated) {
      authAPI.me()
        .then((res) => {
          setUser(res.data)
          setToken(token)
        })
        .catch(() => {
          localStorage.removeItem('access_token')
        })
        .finally(() => {
          setLoading(false)
        })
    } else {
      setLoading(false)
    }
  }, [isAuthenticated, setUser, setToken])

  if (loading) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <ProtectedLayout>{children}</ProtectedLayout>
}

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/financial"
          element={
            <ProtectedRoute>
              <FinancialPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/support"
          element={
            <ProtectedRoute>
              <SupportPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/erp"
          element={
            <ProtectedRoute>
              <ErpPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/policy"
          element={
            <ProtectedRoute>
              <PolicyPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/knowledge-base"
          element={
            <ProtectedRoute>
              <KnowledgeBasePage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/approvals"
          element={
            <ProtectedRoute>
              <ApprovalsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/audit"
          element={
            <ProtectedRoute>
              <AuditPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/dashboard/users"
          element={
            <ProtectedRoute>
              <UsersPage />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Router>
  )
}
