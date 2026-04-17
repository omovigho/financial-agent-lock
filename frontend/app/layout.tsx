import type { Metadata } from 'next'
import './globals.css'
import Navbar from '@/components/Navbar'
import Sidebar from '@/components/Sidebar'

export const metadata: Metadata = {
  title: 'Agent-Lock | Secure AI Financial Operations',
  description: 'Secure AI agent platform for financial, customer support, and ERP operations',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Navbar />
        <div className="flex">
          <Sidebar />
          <main className="flex-1 ml-0 lg:ml-64 pt-16 lg:pt-0">{children}</main>
        </div>
      </body>
    </html>
  )
}
