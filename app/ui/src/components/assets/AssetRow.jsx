import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, FileVideo, Package, Film, Move, AlertCircle, Clock, CheckSquare, Square, MoreVertical, Eye, Play, Volume2, Image, FileText } from 'lucide-react'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import { formatDistanceToNow } from 'date-fns'
import Button from '@/components/ui/Button'
import { useQuery } from '@tanstack/react-query'

// Event type to icon mapping
const EVENT_ICONS = {
  recorded: <FileVideo className="h-3 w-3" />,
  remux_completed: <Package className="h-3 w-3" />,
  proxy_completed: <Film className="h-3 w-3" />,
  move_completed: <Move className="h-3 w-3" />,
  error: <AlertCircle className="h-3 w-3 text-red-500" />,
}

// Event type to color mapping
const EVENT_COLORS = {
  recorded: 'text-blue-500',
  remux_completed: 'text-green-500',
  proxy_completed: 'text-purple-500',
  move_completed: 'text-amber-500',
  error: 'text-red-500',
}

export default function AssetRow({ 
  asset, 
  selected, 
  onToggleSelect, 
  onPreview, 
  onAction,
  showMenu,
  onToggleMenu 
}) {
  const [expanded, setExpanded] = useState(false)
  
  // Fetch timeline for this asset
  const { data: timelineData } = useQuery({
    queryKey: ['asset-timeline', asset.id],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${asset.id}/timeline`)
      if (!res.ok) throw new Error('Failed to fetch timeline')
      return res.json()
    },
    enabled: expanded, // Only fetch when expanded
    staleTime: 60000 // Cache for 1 minute
  })
  
  const timeline = timelineData?.timeline || []
  
  // Get the current file path (following remux and move events)
  const getCurrentPath = () => {
    let path = asset.filepath || asset.abs_path
    
    if (timeline.length > 0) {
      // Process events chronologically to track file path changes
      for (const event of timeline) {
        if (event.event_type === 'remux_completed' && event.payload?.to) {
          // Remux creates a new file at a new location
          path = event.payload.to
        } else if (event.event_type === 'move_completed' && event.payload?.to) {
          // Move changes the location of the current file
          path = event.payload.to
        }
      }
    }
    
    return path
  }
  
  const currentPath = getCurrentPath()
  const filename = currentPath?.split('/').pop() || 'Unknown'
  
  const formatEventDescription = (event) => {
    switch (event.event_type) {
      case 'recorded':
        return `File indexed (${formatDuration(event.payload.duration || 0)}, ${formatBytes(event.payload.size || 0)})`
      case 'remux_completed':
        return `Remuxed to ${event.payload.to?.split('/').pop() || 'output'}`
      case 'proxy_completed':
        return `Proxy created (${event.payload.profile} ${event.payload.resolution})`
      case 'move_completed':
        // Show meaningful path - if it's in streamops folder, show from there
        const fullPath = event.payload.to || 'new location'
        const streamopsIndex = fullPath.indexOf('/streamops/')
        if (streamopsIndex !== -1) {
          // Show path from streamops folder onward
          return `Moved to ${fullPath.substring(streamopsIndex + '/streamops/'.length)}`
        } else {
          // Fallback to last 3 segments for other paths
          return `Moved to ${fullPath.split('/').slice(-3).join('/')}`
        }
      case 'error':
        return `Error: ${event.payload.message || 'Unknown error'}`
      default:
        return event.event_type.replace('_', ' ')
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
        
        {/* Expand chevron */}
        <button
          className="flex-shrink-0"
          onClick={(e) => {
            e.stopPropagation()
            setExpanded(!expanded)
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
            {timeline.length > 0 && (
              <span className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                {timeline.length} {timeline.length === 1 ? 'event' : 'events'}
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
      
      {/* Expandable timeline */}
      {expanded && (
        <div className="px-4 py-3 bg-muted/20 border-t">
          {timeline.length === 0 ? (
            <div className="text-sm text-muted-foreground ml-12">
              No events recorded yet
            </div>
          ) : (
            <div className="space-y-2 ml-12">
              {timeline.map((event, idx) => (
                <div key={idx} className="flex items-start gap-3 text-sm">
                  <div className={`mt-0.5 ${EVENT_COLORS[event.event_type] || 'text-muted-foreground'}`}>
                    {EVENT_ICONS[event.event_type] || <Clock className="h-3 w-3" />}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">
                      {formatEventDescription(event)}
                    </div>
                    <div className="text-muted-foreground text-xs">
                      {formatDistanceToNow(new Date(event.created_at), { addSuffix: true })}
                      {event.job_id && (
                        <span className="ml-2 opacity-50">
                          Job: {event.job_id.slice(0, 8)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
              
              {/* Show current location */}
              <div className="mt-3 pt-3 border-t text-xs text-muted-foreground">
                <div className="flex items-start gap-2">
                  <span className="font-medium">Current location:</span>
                  <span className="break-all">{currentPath}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}