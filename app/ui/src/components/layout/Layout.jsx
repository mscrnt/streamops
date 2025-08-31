import { Outlet } from 'react-router-dom'
import { useEffect } from 'react'
import { useStore } from '@/store/useStore'
import Sidebar from './Sidebar'
import { cn } from '@/lib/utils'

export default function Layout() {
  const { theme, sidebarCollapsed } = useStore()
  
  // Don't initialize WebSocket here - it causes disconnections on navigation

  // Apply theme to document
  useEffect(() => {
    const root = document.documentElement
    root.classList.remove('light', 'dark')
    root.classList.add(theme)
  }, [theme])

  return (
    <div className="h-screen flex bg-background text-foreground">
      {/* Sidebar */}
      <Sidebar />
      
      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Page content - Dashboard has its own TopBar, other pages use Header */}
        <main className="flex-1 overflow-auto">
          <div className="h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
}