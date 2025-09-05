import { useState } from 'react'
import { 
  RefreshCw, 
  FolderSync, 
  PlayCircle,
  StopCircle,
  Trash2,
  Database,
  Zap,
  AlertTriangle,
  CheckCircle
} from 'lucide-react'
import Button from '@/components/ui/Button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/Tooltip'

export default function QuickActions({ onAction, disabled }) {
  const [confirmDialog, setConfirmDialog] = useState(null)
  
  const actions = [
    {
      id: 'restart_watchers',
      label: 'Restart Watchers',
      icon: RefreshCw,
      description: 'Restart all drive watchers',
      variant: 'outline',
      requiresConfirm: false
    },
    {
      id: 'reindex_assets',
      label: 'Reindex Recordings',
      icon: FolderSync,
      description: 'Scan drives and update recordings database',
      variant: 'outline',
      requiresConfirm: true,
      confirmTitle: 'Reindex All Recordings?',
      confirmDescription: 'This will scan all configured drives and update the recordings database. This may take several minutes depending on the number of files.'
    },
    {
      id: 'clear_completed_jobs',
      label: 'Clear Completed',
      icon: CheckCircle,
      description: 'Remove completed jobs from history',
      variant: 'outline',
      requiresConfirm: true,
      confirmTitle: 'Clear Completed Jobs?',
      confirmDescription: 'This will permanently remove all completed jobs from the history. Failed and active jobs will be preserved.'
    },
    {
      id: 'clear_cache',
      label: 'Clear Cache',
      icon: Trash2,
      description: 'Clear temporary cache files',
      variant: 'outline',
      requiresConfirm: true,
      confirmTitle: 'Clear Cache?',
      confirmDescription: 'This will delete all temporary cache files. This is safe but may cause temporary performance reduction while caches rebuild.'
    },
    {
      id: 'optimize_db',
      label: 'Optimize DB',
      icon: Database,
      description: 'Vacuum and analyze database',
      variant: 'outline',
      requiresConfirm: false
    }
  ]
  
  const handleAction = (action) => {
    if (action.requiresConfirm) {
      setConfirmDialog(action)
    } else {
      onAction(action.id)
    }
  }
  
  const handleConfirm = () => {
    if (confirmDialog) {
      onAction(confirmDialog.id)
      setConfirmDialog(null)
    }
  }
  
  return (
    <>
      <div className="flex flex-col space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Quick Actions</h3>
          {disabled && (
            <div className="flex items-center space-x-1 text-xs text-muted-foreground">
              <Zap className="h-3 w-3 animate-pulse" />
              <span>Processing...</span>
            </div>
          )}
        </div>
        
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          <TooltipProvider>
            {actions.map((action) => {
              const Icon = action.icon
              return (
                <Tooltip key={action.id}>
                  <TooltipTrigger asChild>
                    <Button
                      variant={action.variant}
                      size="sm"
                      className="h-auto flex-col py-2 px-3"
                      onClick={() => handleAction(action)}
                      disabled={disabled}
                    >
                      <Icon className="h-4 w-4 mb-1" />
                      <span className="text-xs">{action.label}</span>
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>
                    <p>{action.description}</p>
                  </TooltipContent>
                </Tooltip>
              )
            })}
          </TooltipProvider>
        </div>
      </div>
      
      {/* Confirmation Dialog */}
      <Dialog open={!!confirmDialog} onOpenChange={() => setConfirmDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle className="flex items-center space-x-2">
              <AlertTriangle className="h-5 w-5 text-yellow-500" />
              <span>{confirmDialog?.confirmTitle}</span>
            </DialogTitle>
            <DialogDescription>
              {confirmDialog?.confirmDescription}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDialog(null)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleConfirm}
              disabled={disabled}
            >
              {disabled ? 'Processing...' : 'Confirm'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}