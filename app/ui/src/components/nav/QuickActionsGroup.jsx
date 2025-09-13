import { FileText, FolderSync, Trash2, HardDrive, Database } from 'lucide-react'
import Button from '@/components/ui/Button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useApi } from '@/hooks/useApi'
import toast from 'react-hot-toast'
import LogsViewer from '@/components/logs/LogsViewer'

export default function QuickActionsGroup() {
  const { api } = useApi()
  const queryClient = useQueryClient()
  const [confirmAction, setConfirmAction] = useState(null)
  const [showLogsViewer, setShowLogsViewer] = useState(false)
  
  const actionMutation = useMutation({
    mutationFn: async (action) => {
      const response = await api.post('/system/actions', { action })
      return response.data
    },
    onSuccess: (data, action) => {
      toast.success(data.message || `${action} completed`)
      // Invalidate relevant queries based on action
      switch(action) {
        case 'restart_watchers':
          queryClient.invalidateQueries(['drives'])
          break
        case 'reindex_assets':
          queryClient.invalidateQueries(['assets'])
          break
        case 'clear_completed':
          queryClient.invalidateQueries(['jobs'])
          break
        default:
          queryClient.invalidateQueries(['system'])
      }
    },
    onError: (error) => {
      toast.error(error.message || 'Action failed')
    }
  })
  
  const actions = [
    {
      id: 'view_logs',
      label: 'View Logs',
      icon: FileText,
      description: 'View system log files',
      variant: 'ghost',
      noConfirm: true
    },
    {
      id: 'reindex_assets',
      label: 'Reindex Recordings',
      icon: FolderSync,
      description: (
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
          <p className="mt-3 text-sm">Are you sure you want to reindex recordings?</p>
        </div>
      ),
      variant: 'ghost'
    },
    {
      id: 'clear_cache',
      label: 'Clear Cache',
      icon: HardDrive,
      description: (
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
      ),
      variant: 'ghost'
    },
    {
      id: 'optimize_db',
      label: 'Optimize Database',
      icon: Database,
      description: (
        <div className="space-y-3">
          <p>This action will optimize the SQLite database:</p>
          <ul className="list-disc list-inside space-y-1 text-sm">
            <li>Run VACUUM to rebuild and defragment the database</li>
            <li>Update statistics for better query performance</li>
            <li>Reclaim unused space from deleted records</li>
            <li>Reorganize data for faster access</li>
          </ul>
          <div className="bg-yellow-50 dark:bg-yellow-950/50 border border-yellow-200 dark:border-yellow-800 rounded p-2 mt-3">
            <p className="text-sm text-yellow-800 dark:text-yellow-200">
              <strong>Note:</strong> The database will be briefly locked during optimization. This usually takes just a few seconds.
            </p>
          </div>
          <p className="mt-3 text-sm">Are you sure you want to optimize the database?</p>
        </div>
      ),
      variant: 'ghost'
    }
  ]
  
  const handleAction = (action) => {
    if (action.id === 'view_logs') {
      setShowLogsViewer(true)
    } else if (action.noConfirm) {
      actionMutation.mutate(action.id)
    } else {
      setConfirmAction(action)
    }
  }
  
  const confirmAndExecute = () => {
    if (confirmAction) {
      actionMutation.mutate(confirmAction.id)
      setConfirmAction(null)
    }
  }
  
  return (
    <>
      <div className="px-3 py-2">
        <h2 className="mb-2 px-4 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Quick Actions
        </h2>
        <div className="space-y-1">
          {actions.map((action) => {
            const Icon = action.icon
            return (
              <Button
                key={action.id}
                variant={action.variant}
                size="sm"
                className="w-full justify-start"
                onClick={() => handleAction(action)}
                disabled={actionMutation.isPending}
              >
                <Icon className="mr-2 h-4 w-4" />
                {action.label}
              </Button>
            )
          })}
        </div>
      </div>
      
      <AlertDialog open={!!confirmAction} onOpenChange={() => setConfirmAction(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Confirm Action</AlertDialogTitle>
            <AlertDialogDescription asChild>
              <div>
                {typeof confirmAction?.description === 'string' ? (
                  <>
                    {confirmAction?.description}
                    <br />
                    <br />
                    Are you sure you want to {confirmAction?.label.toLowerCase()}?
                  </>
                ) : (
                  confirmAction?.description
                )}
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmAndExecute}>
              Continue
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
      
      <LogsViewer 
        open={showLogsViewer} 
        onClose={() => setShowLogsViewer(false)} 
      />
    </>
  )
}