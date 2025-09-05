import { NavLink } from 'react-router-dom'
import { 
  LayoutDashboard, 
  FolderOpen, 
  Settings, 
  PlayCircle, 
  HardDrive, 
  Zap,
  ChevronLeft,
  Activity,
  Coffee
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStore } from '@/store/useStore'
import QuickActionsGroup from '@/components/nav/QuickActionsGroup'
import OBSControls from '@/components/nav/OBSControls'

const navigation = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    name: 'Assets',
    href: '/assets',
    icon: FolderOpen,
  },
  {
    name: 'Jobs',
    href: '/jobs',
    icon: PlayCircle,
  },
  {
    name: 'Rules',
    href: '/rules',
    icon: Zap,
  },
  {
    name: 'Drives',
    href: '/drives',
    icon: HardDrive,
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
  },
]

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebar } = useStore()
  
  return (
    <div className={cn(
      "flex flex-col bg-card border-r border-border transition-all duration-200 relative",
      sidebarCollapsed ? "w-16" : "w-64"
    )}>
      {/* Header */}
      <div className="h-16 flex items-center justify-between px-4 border-b border-border">
        {!sidebarCollapsed && (
          <div className="flex items-center space-x-2">
            <Activity className="h-6 w-6 text-primary" />
            <span className="font-semibold text-lg">StreamOps</span>
          </div>
        )}
        <button
          onClick={toggleSidebar}
          className={cn(
            "p-1 rounded-md hover:bg-accent transition-colors",
            sidebarCollapsed && "mx-auto"
          )}
        >
          <ChevronLeft 
            className={cn(
              "h-4 w-4 transition-transform duration-200",
              sidebarCollapsed && "rotate-180"
            )} 
          />
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
        {navigation.map((item) => {
          const Icon = item.icon
          return (
            <NavLink
              key={item.name}
              to={item.href}
              className={({ isActive }) =>
                cn(
                  "flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors relative",
                  "hover:bg-accent hover:text-accent-foreground",
                  isActive
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground",
                  sidebarCollapsed && "justify-center"
                )
              }
              title={sidebarCollapsed ? item.name : undefined}
            >
              <Icon className={cn("h-5 w-5", !sidebarCollapsed && "mr-3")} />
              {!sidebarCollapsed && (
                <span className="truncate">{item.name}</span>
              )}
            </NavLink>
          )
        })}
        
        {/* OBS Controls - only show when sidebar is expanded */}
        {!sidebarCollapsed && (
          <OBSControls />
        )}
        
        {/* Quick Actions Group - only show when sidebar is expanded */}
        {!sidebarCollapsed && (
          <div className="mt-6 border-t pt-4">
            <QuickActionsGroup />
          </div>
        )}
      </nav>

      {/* Footer */}
      <div className="border-t border-border p-4">
        <a
          href="https://buymeacoffee.com/mscrnt"
          target="_blank"
          rel="noopener noreferrer"
          className={cn(
            "flex items-center space-x-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors",
            sidebarCollapsed && "justify-center"
          )}
          title={sidebarCollapsed ? "Buy me a coffee" : undefined}
        >
          <Coffee className="h-5 w-5" />
          {!sidebarCollapsed && <span>Buy me a coffee</span>}
        </a>
      </div>
    </div>
  )
}