import { HardDrive, AlertCircle, CheckCircle, XCircle, Film, Edit, Archive, FolderOpen, Eye } from 'lucide-react'
import { formatBytes } from '@/lib/utils'

export default function DriveTile({ drive, onClick }) {
  // Calculate usage percentage
  const usedBytes = drive.total && drive.free !== undefined ? drive.total - drive.free : 0
  const usagePercent = drive.total 
    ? Math.round((usedBytes / drive.total) * 100)
    : 0
  
  // Determine status icon and color
  const getStatusIcon = () => {
    switch (drive.health) {
      case 'ok':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'warning':
        return <AlertCircle className="h-5 w-5 text-yellow-500" />
      case 'critical':
        return <XCircle className="h-5 w-5 text-red-500" />
      case 'missing':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <HardDrive className="h-5 w-5 text-muted-foreground" />
    }
  }
  
  // Determine progress bar color
  const getProgressColor = () => {
    if (drive.health === 'missing') return 'bg-red-500'
    if (usagePercent >= 90) return 'bg-red-500'
    if (usagePercent >= 75) return 'bg-yellow-500'
    return 'bg-primary'
  }
  
  // Get role icon
  const getRoleIcon = (role) => {
    switch (role) {
      case 'recording':
        return <Film className="h-3 w-3" />
      case 'editing':
        return <Edit className="h-3 w-3" />
      case 'archive':
        return <Archive className="h-3 w-3" />
      case 'backlog':
        return <FolderOpen className="h-3 w-3" />
      default:
        return <FolderOpen className="h-3 w-3" />
    }
  }
  
  // Get role label
  const getRoleLabel = (role) => {
    return role.charAt(0).toUpperCase() + role.slice(1)
  }
  
  return (
    <div 
      className="p-3 rounded-lg border bg-card hover:bg-accent/50 cursor-pointer transition-colors"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      aria-label={`Drive ${drive.label}: ${usagePercent}% used`}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          {getStatusIcon()}
          <div>
            <span className="text-sm font-medium">
              {drive.label || drive.id}
            </span>
            {drive.total_assets > 0 && (
              <span className="text-xs text-muted-foreground ml-2">
                {drive.total_assets} assets
              </span>
            )}
          </div>
        </div>
        {drive.watching && (
          <div className="flex items-center">
            <Eye className="h-3 w-3 text-green-500 mr-1" />
            <span className="text-xs text-green-500">Live</span>
          </div>
        )}
      </div>
      
      {/* Storage Bar */}
      {drive.health !== 'missing' && (
        <>
          <div className="w-full bg-secondary rounded-full h-2 mb-1">
            <div 
              className={`h-2 rounded-full transition-all ${getProgressColor()}`}
              style={{ width: `${Math.min(usagePercent, 100)}%` }}
              role="progressbar"
              aria-valuenow={usagePercent}
              aria-valuemin={0}
              aria-valuemax={100}
            />
          </div>
          
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-muted-foreground">
              {formatBytes(usedBytes)} / {formatBytes(drive.total || 0)}
            </span>
            <span className="text-xs font-medium">
              {usagePercent}%
            </span>
          </div>
        </>
      )}
      
      {/* Role Details */}
      {drive.role_details && drive.role_details.length > 0 && (
        <div className="space-y-1 pt-2 border-t">
          {drive.role_details.map((role) => (
            <div key={role.role} className="flex items-center justify-between text-xs">
              <div className="flex items-center space-x-1">
                {getRoleIcon(role.role)}
                <span className="font-medium">{getRoleLabel(role.role)}</span>
              </div>
              <div className="flex items-center space-x-2">
                <span className="text-muted-foreground truncate max-w-[150px]" title={role.path}>
                  {(() => {
                    // Clean up the path display - show relative to drive root
                    const path = role.path;
                    // Remove /mnt/drive_X/ prefix to get the relative path
                    const relativePath = path.replace(/^\/mnt\/drive_[a-z]\//i, '');
                    // Add ./ prefix to show it's relative
                    return './' + relativePath;
                  })()}
                </span>
                <span className="text-muted-foreground">
                  ({role.asset_count})
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {drive.health === 'missing' && (
        <p className="text-xs text-red-500 mt-2">
          Drive not accessible
        </p>
      )}
    </div>
  )
}