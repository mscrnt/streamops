import { HardDrive, AlertCircle, CheckCircle, XCircle } from 'lucide-react'
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
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />
      case 'critical':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'missing':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <HardDrive className="h-4 w-4 text-muted-foreground" />
    }
  }
  
  // Determine progress bar color
  const getProgressColor = () => {
    if (drive.health === 'missing') return 'bg-red-500'
    if (usagePercent >= 90) return 'bg-red-500'
    if (usagePercent >= 75) return 'bg-yellow-500'
    return 'bg-primary'
  }
  
  return (
    <div 
      className="flex items-center space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 cursor-pointer transition-colors"
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          onClick()
        }
      }}
      aria-label={`Drive ${drive.name}: ${usagePercent}% used, ${drive.health} status`}
    >
      <div className="flex-shrink-0">
        {getStatusIcon()}
      </div>
      
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1">
          <span className="text-sm font-medium truncate">
            {drive.label || drive.id}
          </span>
          <span className="text-xs text-muted-foreground ml-2">
            {drive.role === 'recording' ? 'Rec' : 
             drive.role === 'editing' ? 'Edit' : 
             drive.role === 'archive' ? 'Arc' : 'Data'}
          </span>
        </div>
        
        {drive.health !== 'missing' ? (
          <>
            <div className="w-full bg-secondary rounded-full h-1.5 mb-1">
              <div 
                className={`h-1.5 rounded-full transition-all ${getProgressColor()}`}
                style={{ width: `${Math.min(usagePercent, 100)}%` }}
                role="progressbar"
                aria-valuenow={usagePercent}
                aria-valuemin={0}
                aria-valuemax={100}
              />
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">
                {formatBytes(usedBytes)} / {formatBytes(drive.total || 0)}
              </span>
              <span className="text-xs text-muted-foreground">
                {usagePercent}%
              </span>
            </div>
          </>
        ) : (
          <p className="text-xs text-red-500">
            Drive not accessible
          </p>
        )}
        
        {drive.watcher === 'listening' && (
          <div className="flex items-center mt-1">
            <div className="h-1.5 w-1.5 bg-green-500 rounded-full animate-pulse mr-1" />
            <span className="text-xs text-muted-foreground">Watching</span>
          </div>
        )}
      </div>
    </div>
  )
}