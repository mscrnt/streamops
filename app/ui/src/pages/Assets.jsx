import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Grid3x3, List, Search, Filter, ChevronDown, RefreshCw,
  MoreVertical, Download, Archive, Trash2, Copy, Move,
  Play, Image, Music, FileText, CheckSquare, Square,
  X, ChevronRight, Eye, Loader2, AlertCircle, FolderOpen
} from 'lucide-react'
import { Card, CardContent } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import AssetPreviewDrawer from '@/components/assets/AssetPreviewDrawer'
import AssetActionModal from '@/components/assets/AssetActionModal'
import BulkActionBar from '@/components/assets/BulkActionBar'

export default function Assets() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const { api } = useApi()
  
  // URL params state
  const view = searchParams.get('view') || 'list'
  const search = searchParams.get('search') || ''
  const types = searchParams.get('types') || ''
  const status = searchParams.get('status') || ''
  const tags = searchParams.get('tags') || ''
  const sort = searchParams.get('sort') || 'created_at:desc'
  const page = parseInt(searchParams.get('page') || '1')
  const perPage = parseInt(searchParams.get('per_page') || '50')
  
  // Local state
  const [selectedAssets, setSelectedAssets] = useState(new Set())
  const [previewAssetId, setPreviewAssetId] = useState(null)
  const [actionModal, setActionModal] = useState(null)
  const [showSearch, setShowSearch] = useState(!!search)
  const [showFilters, setShowFilters] = useState(false)
  const [localSearch, setLocalSearch] = useState(search)
  const [activeMenuId, setActiveMenuId] = useState(null)
  
  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setActiveMenuId(null)
    }
    if (activeMenuId) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [activeMenuId])

  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams()
    if (search) params.set('search', search)
    if (types) params.set('types', types)
    if (status) params.set('status', status)
    if (tags) params.set('tags', tags)
    params.set('sort', sort)
    params.set('page', page.toString())
    params.set('per_page', perPage.toString())
    return params.toString()
  }, [search, types, status, tags, sort, page, perPage])
  
  // Fetch assets
  const { data: assetsData, isLoading, error, refetch } = useQuery({
    queryKey: ['assets', queryParams],
    queryFn: async () => {
      const response = await api.get(`/assets/?${queryParams}`)
      return response.data
    },
    keepPreviousData: true,
    staleTime: 10000
  })
  
  // Action mutations
  const actionMutation = useMutation({
    mutationFn: async ({ assetId, action, params }) => {
      const response = await api.post(`/assets/${assetId}/actions`, {
        action,
        params
      })
      return response.data
    },
    onSuccess: (data, variables) => {
      toast.success(`Action "${variables.action}" queued`)
      queryClient.invalidateQueries(['assets'])
      setActionModal(null)
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Action failed')
    }
  })
  
  const bulkActionMutation = useMutation({
    mutationFn: async ({ action, params }) => {
      const response = await api.post('/assets/bulk', {
        ids: Array.from(selectedAssets),
        action,
        params
      })
      return response.data
    },
    onSuccess: (data, variables) => {
      toast.success(data.message || `Bulk ${variables.action} queued`)
      queryClient.invalidateQueries(['assets'])
      setSelectedAssets(new Set())
    },
    onError: (error) => {
      toast.error(error.response?.data?.detail || 'Bulk action failed')
    }
  })
  
  // Update URL params
  const updateParams = useCallback((updates) => {
    const newParams = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value) {
        newParams.set(key, value)
      } else {
        newParams.delete(key)
      }
    })
    setSearchParams(newParams)
  }, [searchParams, setSearchParams])
  
  // Handlers
  const handleSearch = useCallback(() => {
    updateParams({ search: localSearch, page: '1' })
  }, [localSearch, updateParams])
  
  const handleViewChange = useCallback((newView) => {
    updateParams({ view: newView })
  }, [updateParams])
  
  const handleSort = useCallback((newSort) => {
    updateParams({ sort: newSort })
  }, [updateParams])
  
  const handleFilter = useCallback((filterType, value) => {
    updateParams({ [filterType]: value, page: '1' })
  }, [updateParams])
  
  const handlePageChange = useCallback((newPage) => {
    updateParams({ page: newPage.toString() })
    window.scrollTo(0, 0)
  }, [updateParams])
  
  const toggleAssetSelection = useCallback((assetId) => {
    setSelectedAssets(prev => {
      const newSet = new Set(prev)
      if (newSet.has(assetId)) {
        newSet.delete(assetId)
      } else {
        newSet.add(assetId)
      }
      return newSet
    })
  }, [])
  
  const selectAllOnPage = useCallback(() => {
    if (assetsData?.assets) {
      const allIds = new Set(assetsData.assets.map(a => a.id))
      setSelectedAssets(allIds)
    }
  }, [assetsData])
  
  const clearSelection = useCallback(() => {
    setSelectedAssets(new Set())
  }, [])
  
  const handleAssetAction = useCallback((assetId, action) => {
    if (action === 'preview') {
      setPreviewAssetId(assetId)
    } else if (action === 'download') {
      window.open(`/api/assets/${assetId}/download`, '_blank')
    } else {
      setActionModal({ assetId, action })
    }
  }, [])
  
  const handleBulkAction = useCallback((action) => {
    if (selectedAssets.size === 0) {
      toast.error('No assets selected')
      return
    }
    
    if (action === 'thumbnails') {
      // No modal needed for thumbnails
      bulkActionMutation.mutate({ action, params: {} })
    } else {
      setActionModal({ bulk: true, action })
    }
  }, [selectedAssets, bulkActionMutation])
  
  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        if (previewAssetId) {
          setPreviewAssetId(null)
        } else if (actionModal) {
          setActionModal(null)
        } else {
          clearSelection()
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key === 'a') {
        e.preventDefault()
        selectAllOnPage()
      } else if (e.key === 'Delete' && selectedAssets.size > 0) {
        e.preventDefault()
        handleBulkAction('delete')
      }
    }
    
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [previewAssetId, actionModal, selectedAssets, selectAllOnPage, clearSelection, handleBulkAction])
  
  // Asset type icon
  const getAssetIcon = (asset) => {
    if (asset.video_codec) return <Play className="w-4 h-4" />
    if (asset.audio_codec) return <Music className="w-4 h-4" />
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(asset.container)) {
      return <Image className="w-4 h-4" />
    }
    return <FileText className="w-4 h-4" />
  }
  
  // Asset status badge
  const getStatusBadge = (status) => {
    const variants = {
      indexed: 'success',
      pending: 'warning',
      failed: 'destructive',
      archived: 'secondary',
      missing: 'destructive'
    }
    return <Badge variant={variants[status] || 'default'}>{status}</Badge>
  }
  
  // Loading state
  if (isLoading && !assetsData) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-primary" />
          <p className="text-muted-foreground">Loading assets...</p>
        </div>
      </div>
    )
  }
  
  // Error state
  if (error) {
    return (
      <div className="p-6">
        <Card className="border-destructive">
          <CardContent className="p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
              <div className="flex-1">
                <h3 className="font-semibold mb-2">Failed to load assets</h3>
                <p className="text-sm text-muted-foreground mb-4">
                  {error.response?.data?.detail || error.message}
                </p>
                <Button onClick={() => refetch()}>
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }
  
  const assets = assetsData?.assets || []
  const total = assetsData?.total || 0
  const totalPages = Math.ceil(total / perPage)
  
  return (
    <div className="h-full flex flex-col">
      {/* Toolbar */}
      <div className="border-b border-border bg-background sticky top-0 z-10">
        <div className="p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            {/* View toggle */}
            <div className="flex rounded-lg border border-input">
              <Button
                variant={view === 'list' ? 'default' : 'ghost'}
                size="sm"
                className="rounded-r-none"
                onClick={() => handleViewChange('list')}
              >
                <List className="w-4 h-4" />
              </Button>
              <Button
                variant={view === 'grid' ? 'default' : 'ghost'}
                size="sm"
                className="rounded-l-none"
                onClick={() => handleViewChange('grid')}
              >
                <Grid3x3 className="w-4 h-4" />
              </Button>
            </div>
            
            {/* Filters */}
            <Button
              variant={showFilters ? 'default' : 'outline'}
              size="sm"
              onClick={() => setShowFilters(!showFilters)}
            >
              <Filter className="w-4 h-4 mr-2" />
              Filters
              {(types || status || tags) && (
                <Badge variant="secondary" className="ml-2">
                  {[types, status, tags].filter(Boolean).length}
                </Badge>
              )}
            </Button>
            
            {/* Sort */}
            <div className="relative">
              <Button variant="outline" size="sm">
                Sort: {sort.split(':')[0]}
                <ChevronDown className="w-4 h-4 ml-2" />
              </Button>
              {/* Sort dropdown would go here */}
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            {/* Search */}
            {showSearch ? (
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={localSearch}
                  onChange={(e) => setLocalSearch(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Search assets..."
                  className="px-3 py-1.5 text-sm border border-input rounded-lg bg-background"
                  autoFocus
                />
                <Button size="sm" onClick={handleSearch}>
                  Search
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setShowSearch(false)
                    setLocalSearch('')
                    updateParams({ search: '' })
                  }}
                >
                  <X className="w-4 h-4" />
                </Button>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowSearch(true)}
              >
                <Search className="w-4 h-4" />
              </Button>
            )}
            
            {/* Refresh */}
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetch()}
              disabled={isLoading}
            >
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            </Button>
          </div>
        </div>
        
        {/* Filter bar */}
        {showFilters && (
          <div className="px-4 pb-4 flex items-center gap-2 flex-wrap">
            {/* Type filter */}
            <select
              value={types}
              onChange={(e) => handleFilter('types', e.target.value)}
              className="px-3 py-1.5 text-sm border border-input rounded-lg bg-background"
            >
              <option value="">All types</option>
              <option value="video">Video</option>
              <option value="audio">Audio</option>
              <option value="image">Image</option>
              <option value="other">Other</option>
            </select>
            
            {/* Status filter */}
            <select
              value={status}
              onChange={(e) => handleFilter('status', e.target.value)}
              className="px-3 py-1.5 text-sm border border-input rounded-lg bg-background"
            >
              <option value="">All status</option>
              <option value="indexed">Indexed</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
              <option value="archived">Archived</option>
              <option value="missing">Missing</option>
            </select>
            
            {/* Clear filters */}
            {(types || status || tags || search) && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  updateParams({
                    types: '',
                    status: '',
                    tags: '',
                    search: '',
                    page: '1'
                  })
                  setLocalSearch('')
                }}
              >
                Clear all
              </Button>
            )}
          </div>
        )}
      </div>
      
      {/* Bulk action bar */}
      {selectedAssets.size > 0 && (
        <BulkActionBar
          selectedCount={selectedAssets.size}
          onAction={handleBulkAction}
          onSelectAll={selectAllOnPage}
          onClear={clearSelection}
        />
      )}
      
      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {assets.length === 0 ? (
          // Empty state
          <Card>
            <CardContent className="p-12 text-center">
              <FolderOpen className="w-12 h-12 mx-auto mb-4 text-muted-foreground" />
              <h3 className="text-lg font-semibold mb-2">No assets found</h3>
              <p className="text-muted-foreground mb-4">
                {search || types || status || tags
                  ? 'Try adjusting your filters or search query'
                  : 'Record in OBS or drop files into a watched folder'}
              </p>
              {(search || types || status || tags) && (
                <Button
                  onClick={() => {
                    updateParams({
                      search: '',
                      types: '',
                      status: '',
                      tags: '',
                      page: '1'
                    })
                    setLocalSearch('')
                  }}
                >
                  Clear filters
                </Button>
              )}
            </CardContent>
          </Card>
        ) : view === 'list' ? (
          // List view
          <div className="space-y-2">
            {assets.map((asset) => (
              <div
                key={asset.id}
                className={cn(
                  "flex items-center gap-4 p-3 rounded-lg border border-border hover:bg-accent/50 transition-colors",
                  selectedAssets.has(asset.id) && "bg-accent"
                )}
              >
                <button
                  onClick={() => toggleAssetSelection(asset.id)}
                  className="flex-shrink-0"
                >
                  {selectedAssets.has(asset.id) ? (
                    <CheckSquare className="w-5 h-5 text-primary" />
                  ) : (
                    <Square className="w-5 h-5 text-muted-foreground" />
                  )}
                </button>
                
                <div className="flex-shrink-0">
                  {getAssetIcon(asset)}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleAssetAction(asset.id, 'preview')}
                      className="font-medium truncate hover:text-primary transition-colors"
                    >
                      {asset.filename || asset.name || 'Untitled'}
                    </button>
                    {asset.tags?.map(tag => (
                      <Badge key={tag} variant="outline" className="text-xs">
                        {tag}
                      </Badge>
                    ))}
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                    <span>{formatBytes(asset.metadata?.size_bytes || 0)}</span>
                    {asset.metadata?.duration && (
                      <span>{formatDuration(asset.metadata.duration)}</span>
                    )}
                    {asset.metadata?.width && asset.metadata?.height && (
                      <span>{asset.metadata.width}×{asset.metadata.height}</span>
                    )}
                    <span>{formatRelativeTime(asset.updated_at)}</span>
                  </div>
                </div>
                
                <div className="flex-shrink-0">
                  {getStatusBadge(asset.status)}
                </div>
                
                <div className="flex-shrink-0 relative">
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={(e) => {
                      e.stopPropagation()
                      setActiveMenuId(activeMenuId === asset.id ? null : asset.id)
                    }}
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                  {activeMenuId === asset.id && (
                    <div className="absolute right-0 top-10 z-20 w-48 bg-popover border border-border rounded-lg shadow-lg py-1">
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleAssetAction(asset.id, 'preview')
                          setActiveMenuId(null)
                        }}
                      >
                        <Eye className="w-4 h-4 inline mr-2" />
                        Preview
                      </button>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={(e) => {
                          e.stopPropagation()
                          setActionModal({ action: 'remux', assetId: asset.id })
                          setActiveMenuId(null)
                        }}
                      >
                        <RefreshCw className="w-4 h-4 inline mr-2" />
                        Remux
                      </button>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={(e) => {
                          e.stopPropagation()
                          setActionModal({ action: 'proxy', assetId: asset.id })
                          setActiveMenuId(null)
                        }}
                      >
                        <Play className="w-4 h-4 inline mr-2" />
                        Create Proxy
                      </button>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                        onClick={(e) => {
                          e.stopPropagation()
                          setActionModal({ action: 'move', assetId: asset.id })
                          setActiveMenuId(null)
                        }}
                      >
                        <Move className="w-4 h-4 inline mr-2" />
                        Move
                      </button>
                      <div className="h-px bg-border my-1" />
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          setActionModal({ action: 'delete', assetId: asset.id })
                          setActiveMenuId(null)
                        }}
                      >
                        <Trash2 className="w-4 h-4 inline mr-2" />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        ) : (
          // Grid view
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
            {assets.map((asset) => (
              <Card
                key={asset.id}
                className={cn(
                  "relative group cursor-pointer transition-all",
                  selectedAssets.has(asset.id) && "ring-2 ring-primary"
                )}
                onClick={() => handleAssetAction(asset.id, 'preview')}
              >
                <div className="aspect-video bg-muted relative overflow-hidden">
                  {/* Thumbnail would go here */}
                  <div className="absolute inset-0 flex items-center justify-center">
                    {getAssetIcon(asset)}
                  </div>
                  
                  {/* Selection checkbox */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleAssetSelection(asset.id)
                    }}
                    className="absolute top-2 left-2 p-1 bg-background/80 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    {selectedAssets.has(asset.id) ? (
                      <CheckSquare className="w-4 h-4 text-primary" />
                    ) : (
                      <Square className="w-4 h-4" />
                    )}
                  </button>
                  
                  {/* Action menu */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      // For now, show the action modal with a default action
                      setActionModal({ action: 'remux', assetId: asset.id })
                    }}
                    className="absolute top-2 right-2 p-1 bg-background/80 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <MoreVertical className="w-4 h-4" />
                  </button>
                  
                  {/* Status badge */}
                  <div className="absolute bottom-2 right-2">
                    {getStatusBadge(asset.status)}
                  </div>
                </div>
                
                <CardContent className="p-3">
                  <p className="font-medium text-sm truncate">{asset.filename || asset.name || 'Untitled'}</p>
                  <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                    <span>{formatBytes(asset.metadata?.size_bytes || 0)}</span>
                    {asset.metadata?.duration && (
                      <span>{formatDuration(asset.metadata.duration)}</span>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
        
        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between mt-6">
            <p className="text-sm text-muted-foreground">
              Showing {((page - 1) * perPage) + 1}-{Math.min(page * perPage, total)} of {total}
            </p>
            
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
              >
                Previous
              </Button>
              
              {/* Page numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const pageNum = Math.max(1, Math.min(page - 2 + i, totalPages - 4)) + i
                  if (pageNum > totalPages) return null
                  return (
                    <Button
                      key={pageNum}
                      variant={pageNum === page ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => handlePageChange(pageNum)}
                    >
                      {pageNum}
                    </Button>
                  )
                }).filter(Boolean)}
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => handlePageChange(page + 1)}
                disabled={page === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
      
      {/* Preview drawer */}
      {previewAssetId && (
        <AssetPreviewDrawer
          assetId={previewAssetId}
          onClose={() => setPreviewAssetId(null)}
          onAction={handleAssetAction}
        />
      )}
      
      {/* Action modal */}
      {actionModal && (
        <AssetActionModal
          action={actionModal.action}
          assetId={actionModal.assetId}
          bulk={actionModal.bulk}
          selectedCount={selectedAssets.size}
          onConfirm={(params) => {
            if (actionModal.bulk) {
              bulkActionMutation.mutate({ action: actionModal.action, params })
            } else {
              actionMutation.mutate({
                assetId: actionModal.assetId,
                action: actionModal.action,
                params
              })
            }
          }}
          onClose={() => setActionModal(null)}
        />
      )}
    </div>
  )
}