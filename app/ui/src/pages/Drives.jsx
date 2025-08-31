import { useState } from 'react'
import { 
  HardDrive, 
  Plus, 
  FolderOpen, 
  Eye, 
  EyeOff, 
  AlertTriangle,
  CheckCircle,
  MoreHorizontal,
  Folder,
  Activity,
  Info
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input, { FormField } from '@/components/ui/Input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableSkeleton, TableEmpty } from '@/components/ui/Table'
import { useDrives, useRoleAssignments } from '@/hooks/useDrives'
import { formatBytes } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'
import * as Dialog from '@radix-ui/react-dialog'
import toast from 'react-hot-toast'

export default function Drives() {
  // Local state
  const [showAddDialog, setShowAddDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingDrive, setEditingDrive] = useState(null)
  const [newDrive, setNewDrive] = useState({
    name: '',
    path: '',
    watch_enabled: true,
    recursive: true,
    file_patterns: ['*.mp4', '*.mov', '*.avi', '*.mkv'],
    ignore_patterns: ['*.tmp', '.*'],
    auto_index: true,
    auto_proxy: false,
    auto_thumbnail: true,
    webhook_url: '',
    notes: ''
  })

  // API hooks
  const { data: drives, isLoading: drivesLoading } = useDrives()
  const { data: roleAssignments } = useRoleAssignments()

  const handleAddDrive = async () => {
    // This functionality would be handled through role assignment now
    toast.info('Use Settings > Wizard to configure drives')
    setShowAddDialog(false)
  }

  const handleEditDrive = async () => {
    // This functionality would be handled through role assignment now
    toast.info('Use Settings > Wizard to configure drives')
    setShowEditDialog(false)
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
        <Button onClick={() => setShowAddDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Add Drive
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
                <Button onClick={() => setShowAddDialog(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Drive
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

      {/* Add Drive Dialog */}
      <Dialog.Root open={showAddDialog} onOpenChange={setShowAddDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto z-50">
            <Dialog.Title className="text-lg font-semibold mb-4">Add New Drive</Dialog.Title>
            
            <div className="space-y-4">
              <FormField label="Drive Name" required>
                <Input
                  placeholder="e.g., Recording Drive"
                  value={newDrive.name}
                  onChange={(e) => setNewDrive({...newDrive, name: e.target.value})}
                />
              </FormField>
              
              <FormField label="Path" required>
                <Input
                  placeholder="e.g., /mnt/recordings or D:\Recordings"
                  value={newDrive.path}
                  onChange={(e) => setNewDrive({...newDrive, path: e.target.value})}
                />
              </FormField>
              
              <FormField label="Notes">
                <Input
                  placeholder="Optional description"
                  value={newDrive.notes}
                  onChange={(e) => setNewDrive({...newDrive, notes: e.target.value})}
                />
              </FormField>
              
              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="File Patterns (one per line)">
                  <textarea
                    rows={4}
                    className="w-full p-2 text-sm border border-input rounded-md"
                    placeholder="*.mp4&#10;*.mov&#10;*.avi"
                    value={newDrive.file_patterns.join('\n')}
                    onChange={(e) => setNewDrive({...newDrive, file_patterns: e.target.value.split('\n').filter(p => p.trim())})}
                  />
                </FormField>
                
                <FormField label="Ignore Patterns (one per line)">
                  <textarea
                    rows={4}
                    className="w-full p-2 text-sm border border-input rounded-md"
                    placeholder="*.tmp&#10;.*&#10;*.part"
                    value={newDrive.ignore_patterns.join('\n')}
                    onChange={(e) => setNewDrive({...newDrive, ignore_patterns: e.target.value.split('\n').filter(p => p.trim())})}
                  />
                </FormField>
              </div>
              
              <div className="space-y-3">
                <h4 className="font-medium">Watching Options</h4>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newDrive.watch_enabled}
                      onChange={(e) => setNewDrive({...newDrive, watch_enabled: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Enable watching</span>
                  </label>
                  
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newDrive.recursive}
                      onChange={(e) => setNewDrive({...newDrive, recursive: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Watch subdirectories</span>
                  </label>
                </div>
              </div>
              
              <div className="space-y-3">
                <h4 className="font-medium">Automatic Actions</h4>
                <div className="grid gap-3 md:grid-cols-3">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newDrive.auto_index}
                      onChange={(e) => setNewDrive({...newDrive, auto_index: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Auto-index files</span>
                  </label>
                  
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newDrive.auto_proxy}
                      onChange={(e) => setNewDrive({...newDrive, auto_proxy: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Auto-create proxies</span>
                  </label>
                  
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newDrive.auto_thumbnail}
                      onChange={(e) => setNewDrive({...newDrive, auto_thumbnail: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Auto-generate thumbnails</span>
                  </label>
                </div>
              </div>
              
              <FormField label="Webhook URL (optional)">
                <Input
                  placeholder="https://example.com/webhook"
                  value={newDrive.webhook_url}
                  onChange={(e) => setNewDrive({...newDrive, webhook_url: e.target.value})}
                />
              </FormField>
            </div>
            
            <div className="flex justify-end space-x-2 mt-6">
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleAddDrive}
                disabled={!newDrive.name.trim() || !newDrive.path.trim()}
              >
                Add Drive
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Edit Drive Dialog */}
      <Dialog.Root open={showEditDialog} onOpenChange={setShowEditDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto z-50">
            <Dialog.Title className="text-lg font-semibold mb-4">Edit Drive</Dialog.Title>
            
            {editingDrive && (
              <div className="space-y-4">
                <FormField label="Drive Name" required>
                  <Input
                    value={editingDrive.name}
                    onChange={(e) => setEditingDrive({...editingDrive, name: e.target.value})}
                  />
                </FormField>
                
                <FormField label="Path" required>
                  <Input
                    value={editingDrive.path}
                    onChange={(e) => setEditingDrive({...editingDrive, path: e.target.value})}
                  />
                </FormField>
                
                <FormField label="Notes">
                  <Input
                    value={editingDrive.notes || ''}
                    onChange={(e) => setEditingDrive({...editingDrive, notes: e.target.value})}
                  />
                </FormField>
                
                <div className="grid gap-4 md:grid-cols-2">
                  <FormField label="File Patterns (one per line)">
                    <textarea
                      rows={4}
                      className="w-full p-2 text-sm border border-input rounded-md"
                      value={editingDrive.file_patterns?.join('\n') || ''}
                      onChange={(e) => setEditingDrive({...editingDrive, file_patterns: e.target.value.split('\n').filter(p => p.trim())})}
                    />
                  </FormField>
                  
                  <FormField label="Ignore Patterns (one per line)">
                    <textarea
                      rows={4}
                      className="w-full p-2 text-sm border border-input rounded-md"
                      value={editingDrive.ignore_patterns?.join('\n') || ''}
                      onChange={(e) => setEditingDrive({...editingDrive, ignore_patterns: e.target.value.split('\n').filter(p => p.trim())})}
                    />
                  </FormField>
                </div>
                
                <div className="space-y-3">
                  <h4 className="font-medium">Watching Options</h4>
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingDrive.watch_enabled}
                        onChange={(e) => setEditingDrive({...editingDrive, watch_enabled: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Enable watching</span>
                    </label>
                    
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingDrive.recursive}
                        onChange={(e) => setEditingDrive({...editingDrive, recursive: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Watch subdirectories</span>
                    </label>
                  </div>
                </div>
                
                <div className="space-y-3">
                  <h4 className="font-medium">Automatic Actions</h4>
                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingDrive.auto_index}
                        onChange={(e) => setEditingDrive({...editingDrive, auto_index: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Auto-index files</span>
                    </label>
                    
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingDrive.auto_proxy}
                        onChange={(e) => setEditingDrive({...editingDrive, auto_proxy: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Auto-create proxies</span>
                    </label>
                    
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingDrive.auto_thumbnail}
                        onChange={(e) => setEditingDrive({...editingDrive, auto_thumbnail: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Auto-generate thumbnails</span>
                    </label>
                  </div>
                </div>
                
                <FormField label="Webhook URL (optional)">
                  <Input
                    value={editingDrive.webhook_url || ''}
                    onChange={(e) => setEditingDrive({...editingDrive, webhook_url: e.target.value})}
                  />
                </FormField>
              </div>
            )}
            
            <div className="flex justify-end space-x-2 mt-6">
              <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleEditDrive}
                disabled={!editingDrive?.name?.trim() || !editingDrive?.path?.trim()}
              >
                Save Changes
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}