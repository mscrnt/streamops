import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, FileVideo, Package, Film, Move, Copy, AlertCircle, Clock, CheckSquare, Square, MoreVertical, Eye, Play, Volume2, Image, FileText } from 'lucide-react'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'
import Button from '@/components/ui/Button'
import { useQuery } from '@tanstack/react-query'

// Event type to icon mapping
const EVENT_ICONS = {
  indexed: <FileVideo className="h-3 w-3" />,
  remuxed: <Package className="h-3 w-3" />,
  proxy_created: <Film className="h-3 w-3" />,
  moved: <Move className="h-3 w-3" />,
  copied: <Copy className="h-3 w-3" />,
  error: <AlertCircle className="h-3 w-3 text-red-500" />,
}

// Event type to color mapping
const EVENT_COLORS = {
  indexed: 'text-blue-500',
  remuxed: 'text-green-500',
  proxy_created: 'text-purple-500',
  moved: 'text-amber-500',
  copied: 'text-indigo-500',
  error: 'text-red-500',
}

export default function AssetRow({ 
  asset, 
  selected, 
  onToggleSelect, 
  onPreview, 
  onAction,
  showMenu,
  onToggleMenu,
  hideCheckbox = false
}) {
  const [expanded, setExpanded] = useState(false)
  const [, forceUpdate] = useState({})
  
  // Force re-render every minute to update relative times
  useEffect(() => {
    const interval = setInterval(() => {
      forceUpdate({})
    }, 60000) // Update every 60 seconds
    
    return () => clearInterval(interval)
  }, [])
  
  // Fetch history for this asset
  const { data: historyData } = useQuery({
    queryKey: ['asset-history', asset.id],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${asset.id}/history`)
      if (!res.ok) throw new Error('Failed to fetch history')
      return res.json()
    },
    enabled: expanded, // Only fetch when expanded
    staleTime: 60000 // Cache for 1 minute
  })
  
  const history = historyData?.history || []
  
  // Use the current_path from API if available, otherwise fall back to abs_path or filepath
  const currentPath = asset.current_path || asset.filepath || asset.abs_path
  const originalPath = asset.abs_path || asset.filepath
  const filename = currentPath?.split('/').pop() || 'Unknown'
  const hasBeenMoved = currentPath !== originalPath
  
  const formatEventDescription = (event) => {
    switch (event.type) {
      case 'indexed':
        const size = event.details?.size
        const duration = event.details?.duration
        if (size || duration) {
          const parts = []
          if (duration) parts.push(formatDuration(duration))
          if (size) parts.push(formatBytes(size))
          return `${event.description} (${parts.join(', ')})`
        }
        return event.description
      case 'moved':
      case 'copied':
        if (event.details?.location_change) {
          return `${event.description}: ${event.details.location_change}`
        }
        return event.description
      case 'proxy_created':
        if (event.details?.proxy_file) {
          const filename = event.details.proxy_file.split('/').pop()
          return `${event.description}: ${filename}`
        }
        return event.description
      case 'remuxed':
        if (event.details?.to) {
          return `${event.description} to ${event.details.to.split('/').pop()}`
        }
        return event.description
      default:
        return event.description || event.type.replace('_', ' ')
    }
  }
  
  const getAssetIcon = () => {
    if (asset.asset_type === 'video') return <FileVideo className="w-5 h-5 text-muted-foreground" />
    if (asset.asset_type === 'audio') return <Volume2 className="w-5 h-5 text-muted-foreground" />
    if (asset.asset_type === 'image') return <Image className="w-5 h-5 text-muted-foreground" />
    return <FileText className="w-5 h-5 text-muted-foreground" />
  }
  
  const handleRowClick = (e) => {
    // Don't expand if clicking on buttons or checkboxes
    if (e.target.closest('button') || e.target.closest('[role="button"]')) {
      return
    }
    setExpanded(!expanded)
  }
  
  return (
    <div className="border border-border rounded-lg mb-2 hover:bg-accent/30 transition-colors">
      {/* Main row */}
      <div
        className={cn(
          "flex items-center gap-4 p-3 cursor-pointer",
          selected && "bg-accent"
        )}
        onClick={handleRowClick}
      >
        {/* Checkbox */}
        {!hideCheckbox && (
          <button
            onClick={(e) => {
              e.stopPropagation()
              onToggleSelect(asset.id)
            }}
            className="flex-shrink-0"
          >
            {selected ? (
              <CheckSquare className="w-5 h-5 text-primary" />
            ) : (
              <Square className="w-5 h-5 text-muted-foreground" />
            )}
          </button>
        )}
        
        {/* Expand chevron */}
        <button
          className="flex-shrink-0 focus:outline-none"
          onClick={(e) => {
            e.stopPropagation()
            setExpanded(!expanded)
            // Remove focus after click
            e.currentTarget.blur()
          }}
        >
          {expanded ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
        
        {/* Asset icon */}
        {getAssetIcon()}
        
        {/* Asset info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium truncate" title={currentPath}>
              {filename}
            </span>
            {history.length > 0 && (
              <span className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                {history.length} {history.length === 1 ? 'event' : 'events'}
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-3 mt-1 text-sm text-muted-foreground">
            {asset.metadata?.duration && (
              <span>{formatDuration(asset.metadata.duration)}</span>
            )}
            {asset.metadata?.size_bytes && (
              <span>{formatBytes(asset.metadata.size_bytes)}</span>
            )}
            {asset.metadata?.width && asset.metadata?.height && (
              <span>{asset.metadata.width}×{asset.metadata.height}</span>
            )}
            <span>• {formatRelativeTime(asset.created_at)}</span>
          </div>
        </div>
        
        {/* Action buttons */}
        <div className="flex items-center gap-2" onClick={e => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => onPreview(asset.id)}
            className="h-8 w-8"
          >
            <Eye className="h-4 w-4" />
          </Button>
          
          {asset.asset_type === 'video' && (
            <Button
              variant="ghost"
              size="icon"
              onClick={() => onAction(asset.id, 'play')}
              className="h-8 w-8"
            >
              <Play className="h-4 w-4" />
            </Button>
          )}
          
          <div className="relative">
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => {
                e.stopPropagation()
                onToggleMenu(asset.id)
              }}
              className="h-8 w-8"
            >
              <MoreVertical className="h-4 w-4" />
            </Button>
            
            {showMenu && (
              <div className="absolute right-0 top-full mt-1 w-48 rounded-lg border border-border bg-popover p-1 shadow-md z-50">
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => onAction(asset.id, 'remux')}
                >
                  <Package className="h-4 w-4" />
                  Remux
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => onAction(asset.id, 'proxy')}
                >
                  <Film className="h-4 w-4" />
                  Create Proxy
                </button>
                <button
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-accent"
                  onClick={() => onAction(asset.id, 'move')}
                >
                  <Move className="h-4 w-4" />
                  Move
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Expandable history */}
      {expanded && (
        <div className="px-4 py-3 bg-muted/20 border-t">
          {history.length === 0 ? (
            <div className="text-sm text-muted-foreground ml-12">
              No events recorded yet
            </div>
          ) : (
            <div className="space-y-2 ml-12">
              {history.map((event, idx) => (
                <div key={idx} className="flex items-start gap-3 text-sm">
                  <div className={`mt-0.5 ${EVENT_COLORS[event.type] || 'text-muted-foreground'}`}>
                    {EVENT_ICONS[event.type] || <Clock className="h-3 w-3" />}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">
                      {formatEventDescription(event)}
                    </div>
                    {event.details?.original_path && idx === 0 && (
                      <div className="text-muted-foreground text-xs mt-1">
                        Original: {event.details.original_path}
                      </div>
                    )}
                    <div className="text-muted-foreground text-xs">
                      {formatRelativeTime(event.timestamp)}
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Current location */}
              {currentPath && (
                <div className="mt-3 pt-3 border-t text-xs text-muted-foreground">
                  <div className="flex items-start gap-2">
                    <span className="font-medium">Current location:</span>
                    <span className="break-all">{currentPath}</span>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}