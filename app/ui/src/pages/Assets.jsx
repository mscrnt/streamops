import React, { useState, useEffect } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { 
  Search, 
  Filter, 
  Grid, 
  List, 
  Download, 
  Play, 
  MoreHorizontal,
  FileVideo,
  FileAudio,
  File,
  Trash2,
  RefreshCw,
  Tag,
  Clock,
  HardDrive
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { SimpleSelect } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableSkeleton, TableEmpty } from '@/components/ui/Table'
import { useAssets, useAssetSearch, useDeleteAsset, useDownloadAsset, useBulkAssetOperation, useReindexAsset } from '@/hooks/useAssets'
import { useJobTypeOperations } from '@/hooks/useJobs'
import { useStore, useAssetStore } from '@/store/useStore'
import { formatBytes, formatDuration, formatRelativeTime, getFileExtension, isVideoFile, isAudioFile, debounce } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'
import toast from 'react-hot-toast'

export default function Assets() {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  
  // Local state
  const [searchQuery, setSearchQuery] = useState(searchParams.get('search') || '')
  const [viewMode, setViewMode] = useState('list') // 'list' | 'grid'
  const [selectedAssets, setSelectedAssets] = useState([])
  const [isLoading, setIsLoading] = useState(false)
  
  // Store state
  const { assetFilters, setAssetFilters } = useStore()
  
  // API hooks
  const { data: assets, isLoading: assetsLoading, error: assetsError } = useAssets()
  const { data: searchResults, isLoading: searchLoading } = useAssetSearch(searchQuery, {
    type: assetFilters.type,
    limit: 50
  })
  const deleteAsset = useDeleteAsset()
  const downloadAsset = useDownloadAsset()
  const bulkOperation = useBulkAssetOperation()
  const reindexAsset = useReindexAsset()
  const { createRemuxJob, createProxyJob, createThumbnailJob, createTranscodeJob } = useJobTypeOperations()

  // Debounced search - use useCallback to prevent recreating on every render
  const debouncedSearch = React.useCallback(
    debounce((query) => {
      if (query) {
        setSearchParams({ search: query })
      } else {
        setSearchParams({})
      }
    }, 300),
    [setSearchParams]
  )

  useEffect(() => {
    debouncedSearch(searchQuery)
  }, [searchQuery, debouncedSearch])

  // Data to display
  const displayData = searchQuery ? searchResults?.assets : assets?.assets
  const totalCount = searchQuery ? searchResults?.total : assets?.total
  const loading = searchQuery ? searchLoading : assetsLoading

  const handleFilterChange = (key, value) => {
    setAssetFilters({ [key]: value })
  }

  const handleSelectAsset = (assetId) => {
    setSelectedAssets(prev => 
      prev.includes(assetId) 
        ? prev.filter(id => id !== assetId)
        : [...prev, assetId]
    )
  }

  const handleSelectAll = () => {
    if (selectedAssets.length === displayData?.length) {
      setSelectedAssets([])
    } else {
      setSelectedAssets(displayData?.map(asset => asset.id) || [])
    }
  }

  const handleBulkOperation = async (operation) => {
    if (selectedAssets.length === 0) {
      toast.error('No assets selected')
      return
    }

    try {
      setIsLoading(true)
      await bulkOperation.mutateAsync({
        operation,
        assetIds: selectedAssets
      })
      setSelectedAssets([])
    } catch (error) {
      toast.error(`Bulk ${operation} failed`)
    } finally {
      setIsLoading(false)
    }
  }

  const getFileIcon = (filename) => {
    if (isVideoFile(filename)) return FileVideo
    if (isAudioFile(filename)) return FileAudio
    return File
  }

  const sortOptions = [
    { value: 'created_at', label: 'Created Date' },
    { value: 'filename', label: 'Filename' },
    { value: 'file_size', label: 'File Size' },
    { value: 'duration', label: 'Duration' },
  ]

  const typeOptions = [
    { value: 'all', label: 'All Files' },
    { value: 'video', label: 'Videos' },
    { value: 'audio', label: 'Audio' },
    { value: 'image', label: 'Images' },
  ]

  const statusOptions = [
    { value: 'all', label: 'All Status' },
    { value: 'indexed', label: 'Indexed' },
    { value: 'processing', label: 'Processing' },
    { value: 'error', label: 'Error' },
  ]

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Assets</h1>
          <p className="text-muted-foreground">
            Browse and manage your media library
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant={viewMode === 'list' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('list')}
          >
            <List className="h-4 w-4" />
          </Button>
          <Button
            variant={viewMode === 'grid' ? 'default' : 'outline'}
            size="sm"
            onClick={() => setViewMode('grid')}
          >
            <Grid className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col space-y-4 md:flex-row md:space-y-0 md:space-x-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search assets..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>

            {/* Filters */}
            <div className="flex space-x-2">
              <SimpleSelect
                options={typeOptions}
                value={assetFilters.type}
                onValueChange={(value) => handleFilterChange('type', value)}
                placeholder="File Type"
              />
              
              <SimpleSelect
                options={statusOptions}
                value={assetFilters.status}
                onValueChange={(value) => handleFilterChange('status', value)}
                placeholder="Status"
              />
              
              <SimpleSelect
                options={sortOptions}
                value={assetFilters.sortBy}
                onValueChange={(value) => handleFilterChange('sortBy', value)}
                placeholder="Sort By"
              />
            </div>
          </div>

          {/* Bulk Actions */}
          {selectedAssets.length > 0 && (
            <div className="flex items-center justify-between mt-4 p-3 bg-muted rounded-lg">
              <span className="text-sm font-medium">
                {selectedAssets.length} asset{selectedAssets.length > 1 ? 's' : ''} selected
              </span>
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkOperation('create_proxy')}
                  loading={isLoading}
                >
                  Create Proxies
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkOperation('create_thumbnails')}
                  loading={isLoading}
                >
                  Generate Thumbnails
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkOperation('reindex')}
                  loading={isLoading}
                >
                  Reindex
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleBulkOperation('delete')}
                  loading={isLoading}
                >
                  Delete
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Results */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>
              {totalCount ? `${totalCount.toLocaleString()} assets` : 'Assets'}
            </span>
            <Button variant="outline" size="sm" onClick={() => window.location.reload()}>
              <RefreshCw className="h-4 w-4" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <TableSkeleton rows={10} columns={6} />
          ) : !displayData || displayData.length === 0 ? (
            <TableEmpty
              icon={FileVideo}
              title={searchQuery ? 'No assets found' : 'No assets'}
              description={searchQuery ? `No assets match "${searchQuery}"` : 'Your media library is empty'}
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      checked={selectedAssets.length === displayData.length}
                      onChange={handleSelectAll}
                      className="rounded border-border"
                    />
                  </TableHead>
                  <TableHead>Asset</TableHead>
                  <TableHead>Type</TableHead>
                  <TableHead>Size</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayData.map((asset) => {
                  const FileIcon = getFileIcon(asset.filename)
                  const isSelected = selectedAssets.includes(asset.id)
                  
                  return (
                    <TableRow 
                      key={asset.id}
                      className={isSelected ? 'bg-muted/50' : ''}
                    >
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleSelectAsset(asset.id)}
                          className="rounded border-border"
                        />
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          <FileIcon className="h-5 w-5 text-muted-foreground" />
                          <div className="min-w-0">
                            <p className="font-medium truncate max-w-64">{asset.filename}</p>
                            <p className="text-xs text-muted-foreground truncate">
                              {asset.path}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge variant="outline">
                          {getFileExtension(asset.filename).toUpperCase()}
                        </Badge>
                      </TableCell>
                      
                      <TableCell className="text-sm">
                        {formatBytes(asset.file_size)}
                      </TableCell>
                      
                      <TableCell className="text-sm">
                        {asset.duration ? formatDuration(asset.duration) : 'N/A'}
                      </TableCell>
                      
                      <TableCell>
                        <StatusBadge status={asset.status} />
                      </TableCell>
                      
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelativeTime(asset.created_at)}
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
                              onClick={() => downloadAsset.mutate({ assetId: asset.id })}
                            >
                              <Download className="h-4 w-4 mr-2" />
                              Download
                            </DropdownMenuItem>
                            
                            {isVideoFile(asset.filename) && (
                              <>
                                <DropdownMenuItem 
                                  className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                                  onClick={() => createProxyJob.mutate({ assetId: asset.id })}
                                >
                                  <Play className="h-4 w-4 mr-2" />
                                  Create Proxy
                                </DropdownMenuItem>
                                
                                <DropdownMenuItem 
                                  className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                                  onClick={() => createThumbnailJob.mutate({ assetId: asset.id })}
                                >
                                  <FileVideo className="h-4 w-4 mr-2" />
                                  Generate Thumbnails
                                </DropdownMenuItem>
                              </>
                            )}
                            
                            <DropdownMenuSeparator className="h-px bg-border my-1" />
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                              onClick={() => reindexAsset.mutate(asset.id)}
                            >
                              <RefreshCw className="h-4 w-4 mr-2" />
                              Reindex
                            </DropdownMenuItem>
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-destructive hover:text-destructive-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                if (confirm(`Delete "${asset.filename}"?`)) {
                                  deleteAsset.mutate(asset.id)
                                }
                              }}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}