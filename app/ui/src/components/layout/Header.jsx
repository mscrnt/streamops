import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Search, User, Settings, LogOut, Moon, Sun } from 'lucide-react'
import { useStore } from '@/store/useStore'
import { useJobs } from '@/hooks/useJobs'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'

export default function Header() {
  const [searchQuery, setSearchQuery] = useState('')
  const { theme, toggleTheme } = useStore()
  const { data: jobs } = useJobs()
  const navigate = useNavigate()
  
  // Count active jobs
  const activeJobs = jobs?.filter(job => 
    job.status === 'running' || job.status === 'pending'
  )?.length || 0

  const handleSearch = (e) => {
    e.preventDefault()
    if (searchQuery.trim()) {
      // Navigate to recordings page with search using React Router
      navigate(`/recordings?search=${encodeURIComponent(searchQuery)}`)
    }
  }

  return (
    <header className="h-16 bg-background border-b border-border flex items-center justify-between px-6">
      {/* Search */}
      <div className="flex-1 max-w-md">
        <form onSubmit={handleSearch} className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search assets..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-muted rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </form>
      </div>

      {/* Right side */}
      <div className="flex items-center space-x-4">
        {/* Theme toggle */}
        <Button
          variant="ghost"
          size="sm"
          onClick={toggleTheme}
          className="p-2"
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>

        {/* Notifications */}
        <div className="relative">
          <Button variant="ghost" size="sm" className="p-2">
            <Bell className="h-4 w-4" />
            {activeJobs > 0 && (
              <Badge 
                variant="destructive" 
                className="absolute -top-1 -right-1 px-1 min-w-[1.25rem] h-5 text-xs"
              >
                {activeJobs > 99 ? '99+' : activeJobs}
              </Badge>
            )}
          </Button>
        </div>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" size="sm" className="p-2">
              <User className="h-4 w-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent 
            align="end" 
            className="w-48 bg-popover border border-border rounded-md shadow-lg p-1"
          >
            <div className="px-2 py-1.5 text-sm text-muted-foreground">
              StreamOps Admin
            </div>
            <DropdownMenuSeparator className="h-px bg-border my-1" />
            <DropdownMenuItem className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center">
              <Settings className="h-4 w-4 mr-2" />
              Settings
            </DropdownMenuItem>
            <DropdownMenuItem className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center">
              <LogOut className="h-4 w-4 mr-2" />
              Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  )
}