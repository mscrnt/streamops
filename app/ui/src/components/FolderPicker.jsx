import React, { useState, useEffect } from 'react'
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter,
  DialogDescription 
} from '@/components/ui/Dialog'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { useApi } from '@/hooks/useApi'
import { 
  Folder, 
  FolderOpen, 
  File, 
  ChevronRight, 
  ArrowUp,
  Plus,
  HardDrive,
  AlertCircle,
  CheckCircle,
  XCircle,
  Loader2
} from 'lucide-react'

export default function FolderPicker({ 
  open, 
  onClose, 
  onSelect,
  requireWrite = false,
  role = null,
  title = "Select Folder"
}) {
  // Only log when open state changes to true
  useEffect(() => {
    if (open) {
      console.log('[FolderPicker] Dialog opened for role:', role)
    }
  }, [open, role])
  
  const { api } = useApi()
  const [roots, setRoots] = useState([])
  const [selectedRoot, setSelectedRoot] = useState(null)
  const [currentPath, setCurrentPath] = useState('')
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [breadcrumbs, setBreadcrumbs] = useState([])
  const [selectedEntry, setSelectedEntry] = useState(null)
  const [isWritable, setIsWritable] = useState(true)
  const [newFolderName, setNewFolderName] = useState('')
  const [showNewFolder, setShowNewFolder] = useState(false)
  

  // Load available roots on mount
  useEffect(() => {
    console.log('FolderPicker open state changed:', open)
    if (open) {
      loadRoots()
    }
  }, [open])

  // Load directory contents when root or path changes
  useEffect(() => {
    if (selectedRoot && open) {
      loadDirectory()
    }
  }, [selectedRoot, currentPath, open])

  const loadRoots = async () => {
    try {
      setLoading(true)
      console.log('[FolderPicker] Loading drives...')
      const response = await api.get('/drives/discovered')
      console.log('[FolderPicker] Drives response:', response.data)
      const availableRoots = response.data.filter(r => r.online)
      console.log('[FolderPicker] Available roots after filter:', availableRoots)
      setRoots(availableRoots)
      
      // Auto-select first root if only one
      if (availableRoots.length === 1) {
        console.log('[FolderPicker] Auto-selecting single root:', availableRoots[0])
        setSelectedRoot(availableRoots[0])
      }
    } catch (err) {
      setError('Failed to load drives')
      console.error('[FolderPicker] Error loading drives:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadDirectory = async () => {
    if (!selectedRoot) {
      console.log('[FolderPicker] No selectedRoot, skipping loadDirectory')
      return
    }
    
    console.log('[FolderPicker] Loading directory for root:', selectedRoot.id, 'path:', currentPath)
    
    try {
      setLoading(true)
      setError(null)
      
      const response = await api.get('/fs/list', {
        params: {
          root_id: selectedRoot.id,
          path: currentPath
        }
      })
      
      console.log('[FolderPicker] Directory response:', response.data)
      setEntries(response.data.entries)
      setIsWritable(response.data.is_writable)
      
      // Update breadcrumbs
      const parts = currentPath ? currentPath.split('/').filter(Boolean) : []
      setBreadcrumbs(parts)
      
    } catch (err) {
      console.error('[FolderPicker] Failed to load directory:', err)
      setError('Failed to load directory')
      setEntries([])
    } finally {
      setLoading(false)
    }
  }

  const navigateTo = (path) => {
    setCurrentPath(path)
    setSelectedEntry(null)
  }

  const navigateToFolder = (folderName) => {
    const newPath = currentPath 
      ? `${currentPath}/${folderName}`
      : folderName
    navigateTo(newPath)
  }

  const navigateUp = () => {
    const parts = currentPath.split('/').filter(Boolean)
    parts.pop()
    navigateTo(parts.join('/'))
  }

  const navigateToBreadcrumb = (index) => {
    const parts = breadcrumbs.slice(0, index + 1)
    navigateTo(parts.join('/'))
  }

  const handleSelect = () => {
    console.log('[FolderPicker] handleSelect called')
    console.log('[FolderPicker] selectedRoot:', selectedRoot)
    console.log('[FolderPicker] selectedEntry:', selectedEntry)
    console.log('[FolderPicker] currentPath:', currentPath)
    
    if (!selectedRoot) {
      console.warn('[FolderPicker] No selectedRoot, cannot select')
      return
    }
    
    const selection = {
      root_id: selectedRoot.id,
      root_label: selectedRoot.label,
      root_path: selectedRoot.path,
      subpath: selectedEntry ? 
        (currentPath ? `${currentPath}/${selectedEntry.name}` : selectedEntry.name) :
        currentPath,
      absolute_path: selectedEntry && selectedEntry.type === 'dir' ?
        `${selectedRoot.path}/${currentPath}/${selectedEntry.name}`.replace(/\/+/g, '/') :
        `${selectedRoot.path}/${currentPath}`.replace(/\/+/g, '/'),
      writable: selectedEntry ? selectedEntry.writable : isWritable
    }
    
    console.log('[FolderPicker] Created selection:', selection)
    
    // Check write requirement
    if (requireWrite && !selection.writable) {
      console.error('[FolderPicker] Selected folder is not writable')
      setError('Selected folder is not writable')
      return
    }
    
    console.log('[FolderPicker] Calling onSelect with:', selection)
    onSelect(selection)
    handleClose()
  }

  const handleCreateFolder = async () => {
    if (!newFolderName.trim() || !selectedRoot) return
    
    try {
      setLoading(true)
      const folderPath = currentPath 
        ? `${currentPath}/${newFolderName}`
        : newFolderName
        
      await api.post('/fs/ensure-dir', {
        root_id: selectedRoot.id,
        path: folderPath
      })
      
      setShowNewFolder(false)
      setNewFolderName('')
      
      // Reload directory
      await loadDirectory()
      
      // Auto-select the new folder
      const newEntry = entries.find(e => e.name === newFolderName)
      if (newEntry) {
        setSelectedEntry(newEntry)
      }
    } catch (err) {
      setError('Failed to create folder')
    } finally {
      setLoading(false)
    }
  }

  const handleClose = () => {
    setSelectedRoot(null)
    setCurrentPath('')
    setEntries([])
    setSelectedEntry(null)
    setBreadcrumbs([])
    setError(null)
    setShowNewFolder(false)
    setNewFolderName('')
    onClose()
  }

  const formatSize = (bytes) => {
    if (!bytes) return ''
    const units = ['B', 'KB', 'MB', 'GB', 'TB']
    let size = bytes
    let unitIndex = 0
    while (size >= 1024 && unitIndex < units.length - 1) {
      size /= 1024
      unitIndex++
    }
    return `${size.toFixed(1)} ${units[unitIndex]}`
  }

  const formatPath = (root, path) => {
    if (!root) return ''
    const fullPath = path ? `${root.path}/${path}` : root.path
    return fullPath.replace(/\/+/g, '/')
  }

  
  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-4xl h-[600px] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            {title}
            {role && (
              <span className="ml-2 text-sm text-muted-foreground">
                for {role} role
              </span>
            )}
          </DialogTitle>
          <DialogDescription>
            Select a folder from your mounted drives{requireWrite ? ' (write access required)' : ''}
          </DialogDescription>
        </DialogHeader>

        <div className="flex-1 grid grid-cols-[250px,1fr] gap-4 min-h-0">
          {/* Left: Root selector */}
          <div className="border-r pr-4">
            <div className="mb-2 text-sm font-medium">Mounted Drives</div>
            <div className="h-[450px] overflow-auto">
              <div className="space-y-1">
                {roots.map(root => (
                  <button
                    key={root.id}
                    onClick={() => {
                      setSelectedRoot(root)
                      setCurrentPath('')
                      setSelectedEntry(null)
                    }}
                    className={`w-full text-left px-3 py-2 rounded hover:bg-accent transition-colors ${selectedRoot?.id === root.id ? 'bg-accent' : ''}`}
                  >
                    <div className="flex items-center gap-2">
                      <HardDrive className="w-4 h-4" />
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium truncate">
                          {root.label}
                        </div>
                        <div className="text-xs text-muted-foreground truncate">
                          {root.path}
                        </div>
                      </div>
                      {root.access === 'read-only' && (
                        <XCircle className="w-3 h-3 text-destructive" />
                      )}
                    </div>
                    {root.free > 0 && (
                      <div className="text-xs text-muted-foreground mt-1 ml-6">
                        {formatSize(root.free)} free
                      </div>
                    )}
                  </button>
                ))}
                
                {roots.length === 0 && !loading && (
                  <div className="text-sm text-muted-foreground text-center py-8">
                    No drives mounted
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right: Directory browser */}
          <div className="flex flex-col min-h-0">
            {/* Breadcrumbs */}
            {selectedRoot && (
              <div className="flex items-center gap-1 pb-2 mb-2 border-b">
                <button
                  onClick={() => navigateTo('')}
                  className="text-sm hover:text-primary"
                >
                  {selectedRoot.label}
                </button>
                
                {breadcrumbs.map((part, index) => (
                  <React.Fragment key={index}>
                    <ChevronRight className="w-3 h-3 text-muted-foreground" />
                    <button
                      onClick={() => navigateToBreadcrumb(index)}
                      className="text-sm hover:text-primary"
                    >
                      {part}
                    </button>
                  </React.Fragment>
                ))}
              </div>
            )}

            {/* Toolbar */}
            {selectedRoot && (
              <div className="flex items-center gap-2 mb-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={navigateUp}
                  disabled={!currentPath}
                >
                  <ArrowUp className="w-4 h-4 mr-1" />
                  Up
                </Button>
                
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setShowNewFolder(true)}
                  disabled={!isWritable}
                >
                  <Plus className="w-4 h-4 mr-1" />
                  New Folder
                </Button>

                <div className="flex-1" />
                
                <div className="text-xs text-muted-foreground">
                  {formatPath(selectedRoot, currentPath)}
                </div>
              </div>
            )}

            {/* New folder input */}
            {showNewFolder && (
              <div className="flex items-center gap-2 mb-2 p-2 border rounded">
                <Input
                  placeholder="Folder name"
                  value={newFolderName}
                  onChange={(e) => setNewFolderName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCreateFolder()
                    if (e.key === 'Escape') {
                      setShowNewFolder(false)
                      setNewFolderName('')
                    }
                  }}
                  autoFocus
                />
                <Button size="sm" onClick={handleCreateFolder}>
                  Create
                </Button>
                <Button 
                  size="sm" 
                  variant="outline"
                  onClick={() => {
                    setShowNewFolder(false)
                    setNewFolderName('')
                  }}
                >
                  Cancel
                </Button>
              </div>
            )}

            {/* Directory listing */}
            <div className="flex-1 overflow-auto">
              {loading && (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="w-6 h-6 animate-spin" />
                </div>
              )}

              {!loading && selectedRoot && (
                <div className="space-y-1">
                  {entries
                    .filter(e => e.type === 'dir')
                    .map(entry => (
                      <div
                        key={entry.name}
                        className={`flex items-center gap-2 px-3 py-2 rounded cursor-pointer hover:bg-accent transition-colors ${selectedEntry?.name === entry.name ? 'bg-accent' : ''}`}
                        onClick={() => setSelectedEntry(entry)}
                        onDoubleClick={() => navigateToFolder(entry.name)}
                      >
                        <FolderOpen className="w-4 h-4 text-blue-500" />
                        <span className="text-sm flex-1">{entry.name}</span>
                        {entry.writable ? (
                          <CheckCircle className="w-3 h-3 text-success" />
                        ) : (
                          <XCircle className="w-3 h-3 text-destructive" />
                        )}
                      </div>
                    ))}
                    
                  {entries.filter(e => e.type === 'dir').length === 0 && (
                    <div className="text-sm text-muted-foreground text-center py-8">
                      No subfolders in this directory
                    </div>
                  )}
                </div>
              )}

              {!selectedRoot && !loading && (
                <div className="text-sm text-muted-foreground text-center py-8">
                  Select a drive to browse
                </div>
              )}
            </div>

            {/* Status bar */}
            {selectedRoot && (
              <div className="flex items-center gap-4 pt-2 mt-2 border-t text-xs">
                {isWritable ? (
                  <div className="flex items-center gap-1 text-success">
                    <CheckCircle className="w-3 h-3" />
                    <span>Writable</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-destructive">
                    <XCircle className="w-3 h-3" />
                    <span>Read-only</span>
                  </div>
                )}
                
                <div className="text-muted-foreground">
                  {entries.filter(e => e.type === 'dir').length} folders
                </div>
              </div>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg flex items-start gap-2">
            <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400 mt-0.5" />
            <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={handleClose}>
            Cancel
          </Button>
          <Button 
            onClick={handleSelect}
            disabled={
              !selectedRoot || 
              loading || 
              (requireWrite && !isWritable && !selectedEntry?.writable)
            }
          >
            Select {selectedEntry ? 'Folder' : 'Current Directory'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}