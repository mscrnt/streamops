import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  HardDrive, 
  FolderOpen, 
  Check, 
  X, 
  AlertCircle,
  ChevronRight,
  Plus,
  Trash2,
  RefreshCw
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useApi } from '@/hooks/useApi'
import { formatBytes } from '@/lib/utils'

export default function WizardDrives({ data = [], onChange, defaults }) {
  const { api } = useApi()
  const [drives, setDrives] = useState(data.length > 0 ? data : [])
  const [selectedMount, setSelectedMount] = useState(null)
  const [showPicker, setShowPicker] = useState(false)
  
  // Get available mounts
  const { data: mounts, isLoading, refetch } = useQuery({
    queryKey: ['system', 'mounts'],
    queryFn: async () => {
      const response = await api.get('/system/mounts')
      return response.data
    }
  })
  
  useEffect(() => {
    // Initialize with suggested paths if no drives configured
    if (drives.length === 0 && defaults && mounts) {
      const suggestedDrives = []
      
      // Find recording path
      const recordingPath = defaults.recording_paths?.[0]
      if (recordingPath) {
        const mount = mounts.find(m => recordingPath.startsWith(m.path))
        if (mount) {
          suggestedDrives.push({
            id: `drive_${mount.id}`,
            label: `${mount.label} (Recording)`,
            path: recordingPath,
            role: 'recording',
            enabled: true
          })
        }
      }
      
      // Find editing path
      const editingPath = defaults.editing_paths?.[0]
      if (editingPath) {
        const mount = mounts.find(m => editingPath.startsWith(m.path))
        if (mount) {
          suggestedDrives.push({
            id: `drive_${mount.id}_editing`,
            label: `${mount.label} (Editing)`,
            path: editingPath,
            role: 'editing',
            enabled: true
          })
        }
      }
      
      if (suggestedDrives.length > 0) {
        setDrives(suggestedDrives)
        onChange(suggestedDrives)
      }
    }
  }, [defaults, mounts])
  
  const handleAddDrive = (mount, role) => {
    const newDrive = {
      id: `drive_${mount.id}_${role}`,
      label: `${mount.label} (${role.charAt(0).toUpperCase() + role.slice(1)})`,
      path: mount.path,
      role: role,
      enabled: true
    }
    
    const updatedDrives = [...drives.filter(d => d.role !== role), newDrive]
    setDrives(updatedDrives)
    onChange(updatedDrives)
    setShowPicker(false)
    setSelectedMount(null)
  }
  
  const handleRemoveDrive = (driveId) => {
    const updatedDrives = drives.filter(d => d.id !== driveId)
    setDrives(updatedDrives)
    onChange(updatedDrives)
  }
  
  const handleToggleDrive = (driveId) => {
    const updatedDrives = drives.map(d => 
      d.id === driveId ? { ...d, enabled: !d.enabled } : d
    )
    setDrives(updatedDrives)
    onChange(updatedDrives)
  }
  
  const hasRecordingDrive = drives.some(d => d.role === 'recording' && d.enabled)
  const hasEditingDrive = drives.some(d => d.role === 'editing' && d.enabled)
  const isValid = hasRecordingDrive && hasEditingDrive
  
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
  
  return (
    <div className="space-y-6">
      {/* Status Cards */}
      <div className="grid md:grid-cols-2 gap-4">
        <Card className={hasRecordingDrive ? 'border-green-500/50' : ''}>
          <CardHeader>
            <CardTitle className="text-lg flex items-center justify-between">
              Recording Source
              {hasRecordingDrive && <Check className="h-5 w-5 text-green-500" />}
            </CardTitle>
            <CardDescription>
              Where OBS saves your recordings
            </CardDescription>
          </CardHeader>
          <CardContent>
            {drives.filter(d => d.role === 'recording').map(drive => (
              <div key={drive.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div className="flex items-center space-x-3">
                  <HardDrive className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{drive.label}</p>
                    <p className="text-sm text-muted-foreground">{drive.path}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveDrive(drive.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {!hasRecordingDrive && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setSelectedMount('recording')
                  setShowPicker(true)
                }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Select Recording Folder
              </Button>
            )}
          </CardContent>
        </Card>
        
        <Card className={hasEditingDrive ? 'border-green-500/50' : ''}>
          <CardHeader>
            <CardTitle className="text-lg flex items-center justify-between">
              Editing Target
              {hasEditingDrive && <Check className="h-5 w-5 text-green-500" />}
            </CardTitle>
            <CardDescription>
              Where processed files will be moved
            </CardDescription>
          </CardHeader>
          <CardContent>
            {drives.filter(d => d.role === 'editing').map(drive => (
              <div key={drive.id} className="flex items-center justify-between p-3 bg-muted rounded-lg">
                <div className="flex items-center space-x-3">
                  <HardDrive className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="font-medium">{drive.label}</p>
                    <p className="text-sm text-muted-foreground">{drive.path}</p>
                  </div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleRemoveDrive(drive.id)}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            {!hasEditingDrive && (
              <Button
                variant="outline"
                className="w-full"
                onClick={() => {
                  setSelectedMount('editing')
                  setShowPicker(true)
                }}
              >
                <Plus className="h-4 w-4 mr-2" />
                Select Editing Folder
              </Button>
            )}
          </CardContent>
        </Card>
      </div>
      
      {/* Available Mounts */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Available Storage
            <Button variant="ghost" size="sm" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardTitle>
          <CardDescription>
            Detected mount points and their available space
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Mount</TableHead>
                <TableHead>Path</TableHead>
                <TableHead>Free Space</TableHead>
                <TableHead>Access</TableHead>
                <TableHead>Action</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mounts?.map(mount => (
                <TableRow key={mount.id}>
                  <TableCell className="font-medium">
                    <div className="flex items-center space-x-2">
                      <HardDrive className="h-4 w-4 text-muted-foreground" />
                      <span>{mount.label}</span>
                    </div>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">
                    {mount.path}
                  </TableCell>
                  <TableCell>
                    <div className="space-y-1">
                      <div className="text-sm">
                        {formatBytes(mount.free)} / {formatBytes(mount.total)}
                      </div>
                      <div className="w-24 h-2 bg-muted rounded-full">
                        <div 
                          className={`h-2 rounded-full transition-all ${
                            mount.percent > 90 ? 'bg-red-500' :
                            mount.percent > 75 ? 'bg-yellow-500' : 'bg-green-500'
                          }`}
                          style={{ width: `${mount.percent}%` }}
                        />
                      </div>
                    </div>
                  </TableCell>
                  <TableCell>
                    {mount.rw ? (
                      <Badge variant="success">Read/Write</Badge>
                    ) : (
                      <Badge variant="warning">Read Only</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    {mount.rw && (
                      <div className="flex items-center space-x-2">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleAddDrive(mount, 'recording')}
                          disabled={drives.some(d => d.role === 'recording')}
                        >
                          Recording
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleAddDrive(mount, 'editing')}
                          disabled={drives.some(d => d.role === 'editing')}
                        >
                          Editing
                        </Button>
                      </div>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      
      {/* Validation Message */}
      {!isValid && (
        <Card className="border-yellow-500/50 bg-yellow-500/10">
          <CardContent className="py-4">
            <div className="flex items-start space-x-3">
              <AlertCircle className="h-5 w-5 text-yellow-500 mt-0.5" />
              <div>
                <p className="font-medium">Configuration Required</p>
                <p className="text-sm text-muted-foreground">
                  Please select both a recording source and editing target folder to continue.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}