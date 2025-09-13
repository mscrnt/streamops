import { useState } from 'react'
import { 
  FileText, 
  FolderSync, 
  PlayCircle,
  StopCircle,
  Trash2,
  Database,
  Zap,
  AlertTriangle
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
      id: 'view_logs',
      label: 'View Logs',
      icon: FileText,
      description: 'View system log files',
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
      confirmDescription: (
        <div className="space-y-3">
          <p>This action will perform a full reindex of your media library:</p>
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li>Scan all configured recording, editing, and archive drives</li>
            <li>Update file metadata (size, duration, codecs)</li>
            <li>Detect new files that were added outside StreamOps</li>
            <li>Remove database entries for deleted files</li>
            <li>Rebuild the search index</li>
          </ul>
          <div className="bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 rounded p-2 mt-3">
            <p className="text-sm text-blue-800 dark:text-blue-200">
              <strong>Duration:</strong> This may take several minutes depending on the number of files. The UI will remain responsive during indexing.
            </p>
          </div>
        </div>
      )
    },
    {
      id: 'clear_cache',
      label: 'Clear Cache',
      icon: Trash2,
      description: 'Clear temporary cache files',
      variant: 'outline',
      requiresConfirm: true,
      confirmTitle: 'Clear Cache?',
      confirmDescription: (
        <div className="space-y-3">
          <p>This action will clear the following temporary data:</p>
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li>All files in /data/cache directory</li>
            <li>Temporary FFmpeg working files in /tmp</li>
            <li>Old rotated log files (keeps current logs and 1 backup)</li>
          </ul>
          <div className="bg-orange-50 dark:bg-orange-950/50 border border-orange-200 dark:border-orange-800 rounded p-2 mt-3">
            <p className="text-sm text-orange-800 dark:text-orange-200">
              <strong>What's preserved:</strong>
            </p>
            <ul className="list-disc list-inside text-sm mt-1">
              <li>Current log files (*.log)</li>
              <li>Most recent log backup (*.log.1)</li>
              <li>All media files and recordings</li>
              <li>Database and configuration</li>
            </ul>
          </div>
          <div className="bg-green-50 dark:bg-green-950/50 border border-green-200 dark:border-green-800 rounded p-2">
            <p className="text-sm text-green-800 dark:text-green-200">
              <strong>Safe:</strong> This only removes temporary files. No important data will be lost.
            </p>
          </div>
        </div>
      )
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
            <DialogDescription asChild>
              <div>{confirmDialog?.confirmDescription}</div>
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