import { useState } from 'react'
import { 
  HardDrive, 
  FolderOpen, 
  Eye, 
  EyeOff, 
  AlertTriangle,
  CheckCircle,
  MoreHorizontal,
  Folder,
  Activity,
  Plus,
  Video,
  Edit,
  Archive,
  Clock
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableSkeleton, TableEmpty } from '@/components/ui/Table'
import { useDrives, useAssignRole } from '@/hooks/useDrives'
import { formatBytes } from '@/lib/utils'
import FolderPicker from '@/components/FolderPicker'
import * as Dialog from '@radix-ui/react-dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'
import toast from 'react-hot-toast'

export default function Drives() {
  const [showPicker, setShowPicker] = useState(false)
  const [selectedRole, setSelectedRole] = useState(null)
  
  // API hooks
  const { data: drives, isLoading: drivesLoading, refetch } = useDrives()
  const assignRole = useAssignRole()
  
  const handleFolderSelect = async (selection) => {
    if (!selectedRole) return
    
    try {
      await assignRole.mutateAsync({
        role: selectedRole,
        root_id: selection.root_id,
        subpath: selection.subpath,
        watch: selectedRole === 'recording' // Watch recording folder by default
      })
      
      setShowPicker(false)
      setSelectedRole(null)
      refetch()
      toast.success(`${selectedRole} folder assigned successfully`)
    } catch (error) {
      console.error('Failed to assign role:', error)
    }
  }
  
  const openRolePicker = (role) => {
    setSelectedRole(role)
    setShowPicker(true)
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Drives</h1>
          <p className="text-muted-foreground">
            Configure watched folders and storage locations
          </p>
        </div>
        <Button onClick={() => setShowPicker(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Role
        </Button>
      </div>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Drives</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{drives?.length || 0}</div>
            <p className="text-xs text-muted-foreground">
              Configured drives
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Watching</CardTitle>
            <Eye className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {drives?.filter(drive => drive.watching)?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Active monitoring
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Files</CardTitle>
            <Activity className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {drives?.reduce((sum, drive) => sum + (drive.total_assets || 0), 0) || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Indexed files
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
            <HardDrive className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatBytes(drives?.reduce((sum, drive) => sum + ((drive.total || 0) - (drive.free || 0)), 0) || 0)}
            </div>
            <p className="text-xs text-muted-foreground">
              Total storage
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Drives Table */}
      <Card>
        <CardHeader>
          <CardTitle>Storage Drives</CardTitle>
          <CardDescription>
            Manage watched folders and storage locations
          </CardDescription>
        </CardHeader>
        <CardContent>
          {drivesLoading ? (
            <TableSkeleton rows={5} columns={7} />
          ) : !drives || drives.length === 0 ? (
            <TableEmpty
              icon={HardDrive}
              title="No drives configured"
              description="Add your first drive to start monitoring media files"
              action={
                <Button onClick={() => setShowPicker(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Role
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Drive</TableHead>
                  <TableHead>Role Assignments</TableHead>
                  <TableHead>Total Assets</TableHead>
                  <TableHead>Storage</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Health</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {drives.map((drive) => (
                  <TableRow key={drive.id}>
                    <TableCell>
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <Folder className="h-4 w-4 text-muted-foreground" />
                          <p className="font-medium">{drive.label}</p>
                          {drive.watching ? (
                            <Eye className="h-4 w-4 text-green-500" title="Watching" />
                          ) : (
                            <EyeOff className="h-4 w-4 text-gray-500" title="Not watching" />
                          )}
                        </div>
                        <p className="text-xs text-muted-foreground font-mono">
                          {drive.path}
                        </p>
                      </div>
                    </TableCell>
                    
                    <TableCell>
                      {drive.role_details && drive.role_details.length > 0 ? (
                        <div className="rounded-md border border-border/50 overflow-hidden">
                          <table className="w-full text-xs">
                            <tbody className="divide-y divide-border/50">
                              {drive.role_details.map((roleDetail) => (
                                <tr key={roleDetail.role} className="hover:bg-muted/30">
                                  <td className="px-2 py-1.5 w-24">
                                    <Badge variant="outline" className="text-xs font-medium">
                                      {roleDetail.role}
                                    </Badge>
                                  </td>
                                  <td className="px-2 py-1.5">
                                    <code className="text-xs text-muted-foreground">
                                      {roleDetail.path.replace(drive.path + '/', './')}
                                    </code>
                                  </td>
                                  <td className="px-2 py-1.5 text-right text-muted-foreground">
                                    {roleDetail.asset_count}
                                  </td>
                                  <td className="px-2 py-1.5 w-16 text-center">
                                    {roleDetail.watching ? (
                                      <Eye className="h-3 w-3 text-green-500 mx-auto" />
                                    ) : (
                                      <EyeOff className="h-3 w-3 text-gray-400 mx-auto" />
                                    )}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">No roles assigned</span>
                      )}
                    </TableCell>
                    
                    <TableCell className="text-sm">
                      {drive.total_assets?.toLocaleString() || 0}
                    </TableCell>
                    
                    <TableCell className="text-sm">
                      <div className="space-y-1">
                        <div>{formatBytes((drive.total || 0) - (drive.free || 0))} used</div>
                        <div className="text-xs text-muted-foreground">
                          {formatBytes(drive.free || 0)} free
                        </div>
                      </div>
                    </TableCell>
                    
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        <div className={`h-2 w-2 rounded-full ${
                          drive.watcher === 'listening' ? 'bg-green-500' :
                          drive.watcher === 'scanning' ? 'bg-blue-500' :
                          drive.watcher === 'error' ? 'bg-red-500' :
                          'bg-gray-500'
                        }`} />
                        <span className="text-xs">
                          {drive.watcher || 'stopped'}
                        </span>
                      </div>
                    </TableCell>
                    
                    <TableCell>
                      <div className="flex items-center space-x-2">
                        {drive.health === 'ok' && (
                          <CheckCircle className="h-4 w-4 text-green-500" />
                        )}
                        {drive.health === 'warning' && (
                          <AlertTriangle className="h-4 w-4 text-yellow-500" />
                        )}
                        {drive.health === 'critical' && (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                        {drive.health === 'error' && (
                          <AlertTriangle className="h-4 w-4 text-red-500" />
                        )}
                        {drive.health === 'missing' && (
                          <AlertTriangle className="h-4 w-4 text-gray-500" />
                        )}
                        {drive.health === 'read_only' && (
                          <EyeOff className="h-4 w-4 text-orange-500" />
                        )}
                        <span className="text-xs">
                          {drive.health || 'unknown'}
                        </span>
                      </div>
                    </TableCell>
                    
                    <TableCell>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="sm">
                            <MoreHorizontal className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent 
                          align="end"
                          className="w-48 bg-popover border border-border rounded-md shadow-lg p-1"
                        >
                          <DropdownMenuItem 
                            className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                            onClick={() => {
                              // View drive details
                              toast.info('Drive details coming soon')
                            }}
                          >
                            <FolderOpen className="h-4 w-4 mr-2" />
                            View Details
                          </DropdownMenuItem>
                          
                          <DropdownMenuItem 
                            className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                            onClick={() => {
                              // Force rescan
                              toast.info('Force scan coming soon')
                            }}
                          >
                            <Activity className="h-4 w-4 mr-2" />
                            Force Scan
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Role Assignment Modal */}
      {!selectedRole && showPicker && (
        <Dialog.Root open={showPicker} onOpenChange={setShowPicker}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
            <Dialog.Content className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-md z-50">
              <Dialog.Title className="text-lg font-semibold mb-4">Select Folder Role</Dialog.Title>
              <Dialog.Description className="text-sm text-muted-foreground mb-6">
                Choose what type of folder you want to add
              </Dialog.Description>
              
              <div className="grid gap-3">
                <button
                  onClick={() => openRolePicker('recording')}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left"
                >
                  <Video className="h-5 w-5 text-blue-500 mt-0.5" />
                  <div>
                    <div className="font-medium">Recording Source</div>
                    <div className="text-sm text-muted-foreground">Where OBS saves your recordings</div>
                  </div>
                </button>
                
                <button
                  onClick={() => openRolePicker('editing')}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left"
                >
                  <Edit className="h-5 w-5 text-green-500 mt-0.5" />
                  <div>
                    <div className="font-medium">Editing Target</div>
                    <div className="text-sm text-muted-foreground">Where processed files will be moved</div>
                  </div>
                </button>
                
                <button
                  onClick={() => openRolePicker('archive')}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left"
                >
                  <Archive className="h-5 w-5 text-purple-500 mt-0.5" />
                  <div>
                    <div className="font-medium">Archive</div>
                    <div className="text-sm text-muted-foreground">Long-term storage location</div>
                  </div>
                </button>
                
                <button
                  onClick={() => openRolePicker('backlog')}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left"
                >
                  <Clock className="h-5 w-5 text-orange-500 mt-0.5" />
                  <div>
                    <div className="font-medium">Backlog</div>
                    <div className="text-sm text-muted-foreground">Files awaiting processing</div>
                  </div>
                </button>
                
                <button
                  onClick={() => openRolePicker('assets')}
                  className="flex items-start gap-3 p-4 rounded-lg border border-border hover:bg-accent/50 transition-colors text-left"
                >
                  <Folder className="h-5 w-5 text-indigo-500 mt-0.5" />
                  <div>
                    <div className="font-medium">Assets</div>
                    <div className="text-sm text-muted-foreground">Reusable media files (logos, overlays, etc.)</div>
                  </div>
                </button>
              </div>
              
              <div className="flex justify-end mt-6">
                <Button variant="outline" onClick={() => setShowPicker(false)}>
                  Cancel
                </Button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}

      {/* Folder Picker Modal */}
      {selectedRole && showPicker && (
        <FolderPicker
          open={showPicker}
          onClose={() => {
            setShowPicker(false)
            setSelectedRole(null)
          }}
          onSelect={handleFolderSelect}
          requireWrite={['recording', 'editing', 'archive', 'assets'].includes(selectedRole)}
          role={selectedRole}
          title={`Select ${selectedRole.charAt(0).toUpperCase() + selectedRole.slice(1)} Folder`}
        />
      )}
    </div>
  )
}