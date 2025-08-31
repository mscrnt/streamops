import { RefreshCw, FolderSync, Image, Trash2, HardDrive, Database } from 'lucide-react'
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

export default function QuickActionsGroup() {
  const { api } = useApi()
  const queryClient = useQueryClient()
  const [confirmAction, setConfirmAction] = useState(null)
  
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
        case 'regenerate_thumbnails':
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
      id: 'restart_watchers',
      label: 'Restart Watchers',
      icon: RefreshCw,
      description: 'Restart all folder watchers to detect new files',
      variant: 'ghost'
    },
    {
      id: 'reindex_assets',
      label: 'Reindex Assets',
      icon: FolderSync,
      description: 'Scan all drives and rebuild the asset index',
      variant: 'ghost'
    },
    {
      id: 'regenerate_thumbnails',
      label: 'Regenerate Thumbnails',
      icon: Image,
      description: 'Create missing thumbnails for all assets',
      variant: 'ghost'
    },
    {
      id: 'clear_completed',
      label: 'Clear Completed',
      icon: Trash2,
      description: 'Remove all completed jobs from history',
      variant: 'ghost'
    },
    {
      id: 'clear_cache',
      label: 'Clear Cache',
      icon: HardDrive,
      description: 'Delete temporary files and free up space',
      variant: 'ghost'
    },
    {
      id: 'optimize_db',
      label: 'Optimize Database',
      icon: Database,
      description: 'Vacuum and optimize the database',
      variant: 'ghost'
    }
  ]
  
  const handleAction = (action) => {
    setConfirmAction(action)
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
            <AlertDialogDescription>
              {confirmAction?.description}
              <br />
              <br />
              Are you sure you want to {confirmAction?.label.toLowerCase()}?
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
    </>
  )
}