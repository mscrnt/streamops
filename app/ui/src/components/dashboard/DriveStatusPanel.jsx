import { HardDrive, AlertCircle, CheckCircle, XCircle, Film, Edit, Archive, FolderOpen, Settings } from 'lucide-react'
import { formatBytes } from '@/lib/utils'
import { useDrives } from '@/hooks/useDrives'
import { Link } from 'react-router-dom'
import Button from '@/components/ui/Button'

export default function DriveStatusPanel() {
  const { data: drives, isLoading } = useDrives()
  
  const getStatusIcon = (health) => {
    switch (health) {
      case 'ok':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />
      case 'critical':
      case 'missing':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <HardDrive className="h-4 w-4 text-muted-foreground" />
    }
  }
  
  const getRoleIcon = (role) => {
    switch (role) {
      case 'recording':
        return <Film className="h-3 w-3" />
      case 'editing':
        return <Edit className="h-3 w-3" />
      case 'archive':
        return <Archive className="h-3 w-3" />
      case 'backlog':
      case 'assets':
        return <FolderOpen className="h-3 w-3" />
      default:
        return <FolderOpen className="h-3 w-3" />
    }
  }
  
  const getRoleLabel = (role) => {
    return role.charAt(0).toUpperCase() + role.slice(1)
  }
  
  const getProgressColor = (percent) => {
    if (percent >= 90) return 'bg-red-500'
    if (percent >= 75) return 'bg-yellow-500'
    return 'bg-primary'
  }
  
  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3">Drive Status</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-20 bg-muted rounded"></div>
          <div className="h-20 bg-muted rounded"></div>
        </div>
      </div>
    )
  }
  
  const driveList = drives || []
  
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Drive Status</h3>
        <Link to="/drives">
          <Button variant="ghost" size="sm" className="h-7 text-xs">
            Manage
          </Button>
        </Link>
      </div>
      
      {driveList.length === 0 ? (
        <div className="text-center py-8">
          <HardDrive className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
          <p className="text-sm text-muted-foreground">No drives configured</p>
        </div>
      ) : (
        <div className="space-y-3">
          {driveList.map((drive) => {
            const usedBytes = drive.total && drive.free !== undefined ? drive.total - drive.free : 0
            const usagePercent = drive.total ? Math.round((usedBytes / drive.total) * 100) : 0
            
            return (
              <div key={drive.id} className="space-y-2">
                {/* Drive header */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    {getStatusIcon(drive.health)}
                    <span className="text-sm font-medium">
                      {drive.label || drive.id}
                    </span>
                    {drive.health === 'missing' && (
                      <span className="text-xs text-red-500">Offline</span>
                    )}
                  </div>
                  <span className="text-xs text-muted-foreground">
                    {drive.total_assets || 0} assets
                  </span>
                </div>
                
                {/* Storage bar */}
                {drive.health !== 'missing' && (
                  <>
                    <div className="w-full bg-secondary rounded-full h-1.5">
                      <div 
                        className={`h-1.5 rounded-full transition-all ${getProgressColor(usagePercent)}`}
                        style={{ width: `${Math.min(usagePercent, 100)}%` }}
                      />
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground">
                        {formatBytes(usedBytes)} / {formatBytes(drive.total || 0)}
                      </span>
                      <span className="text-xs font-medium">
                        {usagePercent}%
                      </span>
                    </div>
                  </>
                )}
                
                {/* Role chips */}
                {drive.role_details && drive.role_details.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {drive.role_details.map((role) => (
                      <div
                        key={role.role}
                        className="inline-flex items-center gap-1 rounded-md bg-muted/50 px-2 py-0.5"
                        title={`${role.path} (${role.asset_count} assets)`}
                      >
                        {getRoleIcon(role.role)}
                        <span className="text-xs font-medium">
                          {getRoleLabel(role.role)}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          ({role.asset_count})
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}