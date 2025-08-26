import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  HardDrive, 
  FolderOpen, 
  Check, 
  X, 
  AlertCircle,
  ChevronRight,
  Plus,
  Trash2,
  RefreshCw,
  Folder,
  Edit
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useApi } from '@/hooks/useApi'
import { formatBytes, cn } from '@/lib/utils'
import FolderPicker from '@/components/FolderPicker'

export default function WizardDrives({ data = [], onChange }) {
  const { api } = useApi()
  const [showPicker, setShowPicker] = useState(false)
  const [currentRole, setCurrentRole] = useState(null)
  
  // Get current role assignments
  const { data: rolesData, isLoading, refetch } = useQuery({
    queryKey: ['drives', 'roles'],
    queryFn: async () => {
      console.log('[WizardDrives] Fetching roles...')
      const response = await api.get('/drives/roles')
      console.log('[WizardDrives] Roles response:', response.data)
      return response.data
    }
  })
  
  // Get available drives
  const { data: drivesData } = useQuery({
    queryKey: ['drives', 'discovered'],
    queryFn: async () => {
      console.log('[WizardDrives] Fetching discovered drives...')
      const response = await api.get('/drives/discovered')
      console.log('[WizardDrives] Discovered drives:', response.data)
      return response.data
    }
  })
  
  // Mutation for assigning roles
  const assignRoleMutation = useMutation({
    mutationFn: async ({ role, root_id, subpath, watch }) => {
      console.log('[WizardDrives] Mutation sending request:', {
        role,
        root_id,
        subpath,
        watch: watch !== false
      })
      const response = await api.post('/drives/assign-role', {
        role,
        root_id,
        subpath,
        watch: watch !== false // Default to true
      })
      console.log('[WizardDrives] Mutation response:', response.data)
      return response.data
    },
    onSuccess: (data) => {
      console.log('[WizardDrives] Mutation successful:', data)
      refetch()
    },
    onError: (error) => {
      console.error('[WizardDrives] Mutation error:', error)
      console.error('[WizardDrives] Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status
      })
    }
  })
  
  // Update parent when roles change
  useEffect(() => {
    if (rolesData?.roles && onChange) {
      const assignments = Object.entries(rolesData.roles)
        .filter(([_, assignment]) => assignment !== null)
        .map(([role, assignment]) => ({
          role,
          ...assignment
        }))
      onChange(assignments)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rolesData?.roles]) // Intentionally omit onChange to prevent infinite loops
  
  const handleFolderSelect = async (selection) => {
    console.log('[WizardDrives] handleFolderSelect called with:', selection)
    console.log('[WizardDrives] Current role:', currentRole)
    
    if (!currentRole) {
      console.warn('[WizardDrives] No current role set, cannot assign')
      return
    }
    
    try {
      console.log('[WizardDrives] Assigning role:', {
        role: currentRole,
        root_id: selection.root_id,
        subpath: selection.subpath,
        watch: currentRole === 'recording'
      })
      
      const result = await assignRoleMutation.mutateAsync({
        role: currentRole,
        root_id: selection.root_id,
        subpath: selection.subpath,
        watch: currentRole === 'recording' // Watch recording folder by default
      })
      
      console.log('[WizardDrives] Role assigned successfully:', result)
      
      setShowPicker(false)
      setCurrentRole(null)
    } catch (error) {
      console.error('[WizardDrives] Failed to assign role:', error)
    }
  }
  
  const openFolderPicker = useCallback((role) => {
    console.log('[WizardDrives] openFolderPicker called with role:', role)
    // Set both states together to avoid race conditions
    setCurrentRole(role)
    setShowPicker(true)
    console.log('[WizardDrives] States set - will trigger re-render')
  }, []) // Empty deps - we don't need to recreate this function
  
  const removeRoleAssignment = async (role) => {
    try {
      await api.delete(`/drives/roles/${role}`)
      refetch()
    } catch (err) {
      console.error('Failed to remove role:', err)
    }
  }
  
  const roles = rolesData?.roles || {}
  const hasRecording = roles.recording && roles.recording.exists
  const hasEditing = roles.editing && roles.editing.exists
  const hasArchive = roles.archive && roles.archive.exists
  const isValid = hasRecording && hasEditing
  
  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        </CardContent>
      </Card>
    )
  }
  
  const RoleCard = ({ role, title, description, required = false }) => {
    const assignment = roles[role]
    const isConfigured = assignment && assignment.exists
    
    return (
      <Card className={cn(
        "transition-colors",
        isConfigured && "border-success/50"
      )}>
        <CardHeader>
          <CardTitle className="text-lg flex items-center justify-between">
            <span>{title}</span>
            {isConfigured && <Check className="h-5 w-5 text-success" />}
          </CardTitle>
          <CardDescription>{description}</CardDescription>
        </CardHeader>
        <CardContent>
          {assignment ? (
            <div className="space-y-3">
              <div className="p-3 bg-muted rounded-lg">
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <Folder className="h-5 w-5 text-muted-foreground mt-0.5" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{assignment.drive_label}</p>
                      <p className="text-sm text-muted-foreground truncate">
                        {assignment.abs_path}
                      </p>
                      <div className="flex items-center gap-2 mt-2">
                        {assignment.exists ? (
                          <Badge variant="success" className="text-xs">
                            <Check className="w-3 h-3 mr-1" />
                            Exists
                          </Badge>
                        ) : (
                          <Badge variant="destructive" className="text-xs">
                            <X className="w-3 h-3 mr-1" />
                            Missing
                          </Badge>
                        )}
                        {assignment.writable ? (
                          <Badge variant="success" className="text-xs">
                            Writable
                          </Badge>
                        ) : (
                          <Badge variant="warning" className="text-xs">
                            Read-only
                          </Badge>
                        )}
                        {assignment.watch && (
                          <Badge className="text-xs">
                            Watching
                          </Badge>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => openFolderPicker(role)}
                    >
                      <Edit className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeRoleAssignment(role)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <Button
              variant="outline"
              className="w-full"
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                console.log('Button clicked directly for role:', role)
                openFolderPicker(role)
              }}
            >
              <Plus className="h-4 w-4 mr-2" />
              Select {title} Folder
            </Button>
          )}
        </CardContent>
      </Card>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Required Roles */}
      <div className="grid md:grid-cols-2 gap-4">
        <RoleCard
          role="recording"
          title="Recording Source"
          description="Where OBS saves your recordings"
          required={true}
        />
        
        <RoleCard
          role="editing"
          title="Editing Target"
          description="Where processed files will be moved"
          required={true}
        />
      </div>
      
      {/* Optional Roles */}
      <div className="grid md:grid-cols-3 gap-4">
        <RoleCard
          role="archive"
          title="Archive"
          description="Long-term storage"
        />
        
        <RoleCard
          role="backlog"
          title="Backlog"
          description="Files awaiting processing"
        />
        
        <RoleCard
          role="assets"
          title="Assets"
          description="Reusable media files"
        />
      </div>
      
      {/* Available Drives Summary */}
      {drivesData && drivesData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Mounted Drives
              <Button variant="ghost" size="sm" onClick={() => refetch()}>
                <RefreshCw className="h-4 w-4" />
              </Button>
            </CardTitle>
            <CardDescription>
              Available storage locations detected in your system
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Drive</TableHead>
                  <TableHead>Path</TableHead>
                  <TableHead>Free Space</TableHead>
                  <TableHead>Access</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drivesData.map(drive => (
                  <TableRow key={drive.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <HardDrive className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">{drive.label}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {drive.path}
                    </TableCell>
                    <TableCell>
                      {drive.online ? (
                        <div className="space-y-1">
                          <div className="text-sm">
                            {formatBytes(drive.free)} / {formatBytes(drive.total)}
                          </div>
                          {drive.total > 0 && (
                            <div className="w-24 h-2 bg-muted rounded-full">
                              <div 
                                className={cn(
                                  "h-2 rounded-full transition-all",
                                  (drive.total - drive.free) / drive.total > 0.9 ? 'bg-destructive' :
                                  (drive.total - drive.free) / drive.total > 0.75 ? 'bg-warning' : 
                                  'bg-success'
                                )}
                                style={{ 
                                  width: `${Math.round(((drive.total - drive.free) / drive.total) * 100)}%` 
                                }}
                              />
                            </div>
                          )}
                        </div>
                      ) : (
                        <Badge variant="destructive">Offline</Badge>
                      )}
                    </TableCell>
                    <TableCell>
                      {drive.access === 'read-write' ? (
                        <Badge variant="success">Read/Write</Badge>
                      ) : drive.access === 'read-only' ? (
                        <Badge variant="warning">Read Only</Badge>
                      ) : (
                        <Badge variant="destructive">No Access</Badge>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
      
      {/* Validation Message */}
      {!isValid && (
        <Card className="border-warning/50 bg-warning/10">
          <CardContent className="py-4">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-warning mt-0.5" />
              <div>
                <p className="font-medium">Configuration Required</p>
                <p className="text-sm text-muted-foreground">
                  Please select at least a Recording Source and Editing Target folder to continue.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
      
      {/* Folder Picker Modal */}
      <FolderPicker
        open={showPicker}
        onClose={() => {
          setShowPicker(false)
          setCurrentRole(null)
        }}
        onSelect={handleFolderSelect}
        requireWrite={['recording', 'editing', 'archive'].includes(currentRole)}
        role={currentRole}
        title={`Select ${currentRole ? currentRole.charAt(0).toUpperCase() + currentRole.slice(1) : ''} Folder`}
      />
    </div>
  )
}