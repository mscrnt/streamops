import { useState } from 'react'
import { MoreVertical, RefreshCw, FileVideo, FolderOpen, ExternalLink, Film, ChevronDown, ChevronRight, Check, AlertCircle, Clock, Package, Move, Play } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Button from '@/components/ui/Button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from 'react-router-dom'
import { formatBytes, formatDuration } from '@/lib/utils'

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

export default function RecentRecordingsPanel() {
  const navigate = useNavigate()
  const [expandedAssets, setExpandedAssets] = useState(new Set())
  
  // Fetch recent assets with timelines
  const { data, isLoading, refetch } = useQuery({
    queryKey: ['assets', 'recent-timeline'],
    queryFn: async () => {
      const res = await fetch('/api/assets/recent-timeline?hours=24&limit=10')
      if (!res.ok) throw new Error('Failed to fetch recent assets')
      return res.json()
    },
    refetchInterval: 30000 // Refresh every 30 seconds
  })
  
  const recordings = data?.assets || []
  
  // Toggle timeline expansion
  const toggleTimeline = (assetId) => {
    setExpandedAssets(prev => {
      const next = new Set(prev)
      if (next.has(assetId)) {
        next.delete(assetId)
      } else {
        next.add(assetId)
      }
      return next
    })
  }
  
  // Extract drive letter from filepath
  const getDriveLetter = (filepath) => {
    if (!filepath) return null
    const match = filepath.match(/\/mnt\/drive_([a-z])\//i)
    if (match) {
      return match[1].toUpperCase()
    }
    return null
  }
  
  const getQualityBadge = (metadata) => {
    if (!metadata) return null
    const height = metadata.height
    if (height >= 2160) return '4K'
    if (height >= 1440) return '2K'
    if (height >= 1080) return 'HD'
    if (height >= 720) return 'HD'
    return 'SD'
  }
  
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
  
  const handleOpen = (asset) => {
    navigate(`/recordings/${asset.id}`)
  }
  
  const handleLocate = (asset) => {
    const filename = asset.abs_path?.split('/').pop() || ''
    navigate(`/recordings?search=${encodeURIComponent(filename)}`)
  }
  
  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Recent Recordings</h3>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Link to="/recordings?filter=recording&sort=created_at:desc">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Content with internal scroll */}
      <div className="max-h-[500px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="animate-pulse text-sm text-muted-foreground">Loading recordings...</div>
          </div>
        ) : recordings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-center p-4">
            <Film className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              No recent recordings from watched folders.
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {recordings.map(({ asset, timeline }) => {
              const isExpanded = expandedAssets.has(asset.id)
              const filename = asset.abs_path?.split('/').pop() || 'Unknown'
              
              return (
                <div key={asset.id} className="hover:bg-muted/30">
                  {/* Main asset row */}
                  <div
                    className="flex items-center gap-3 px-4 py-2 cursor-pointer group"
                    onClick={() => toggleTimeline(asset.id)}
                  >
                    <button className="flex-shrink-0 p-0.5">
                      {isExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3" />
                      )}
                    </button>
                    
                    <FileVideo className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                    
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate" title={asset.abs_path}>
                          {filename}
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-2 mt-1 flex-wrap">
                        {/* Drive badge */}
                        {getDriveLetter(asset.abs_path) && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300">
                            Drive {getDriveLetter(asset.abs_path)}
                          </span>
                        )}
                        
                        {/* Quality badge */}
                        {getQualityBadge(asset) && (
                          <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                            {getQualityBadge(asset)}
                          </span>
                        )}
                        
                        {/* Duration */}
                        {asset.duration_sec && (
                          <span className="text-xs text-muted-foreground">
                            {formatDuration(asset.duration_sec)}
                          </span>
                        )}
                        
                        {/* Size */}
                        {asset.size && (
                          <span className="text-xs text-muted-foreground">
                            {formatBytes(asset.size)}
                          </span>
                        )}
                        
                        {/* Time ago */}
                        <span className="text-xs text-muted-foreground">
                          • {formatDistanceToNow(new Date(asset.created_at), { addSuffix: true })}
                        </span>
                        
                        {/* Event count badge */}
                        {timeline.length > 0 && (
                          <span className="inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                            {timeline.length} {timeline.length === 1 ? 'event' : 'events'}
                          </span>
                        )}
                      </div>
                    </div>
                    
                    <div className="opacity-0 group-hover:opacity-100 transition-opacity">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
                          <Button variant="ghost" size="icon" className="h-8 w-8">
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onClick={(e) => {
                            e.stopPropagation()
                            handleOpen(asset)
                          }}>
                            <ExternalLink className="mr-2 h-4 w-4" />
                            Open
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => {
                            e.stopPropagation()
                            handleLocate(asset)
                          }}>
                            <FolderOpen className="mr-2 h-4 w-4" />
                            Locate in Assets
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                  
                  {/* Expandable timeline */}
                  {isExpanded && timeline.length > 0 && (
                    <div className="px-4 py-2 bg-muted/20 border-t">
                      <div className="space-y-2 ml-10">
                        {timeline.map((event, idx) => (
                          <div key={idx} className="flex items-start gap-3 text-xs">
                            <div className={`mt-0.5 ${EVENT_COLORS[event.event_type] || 'text-muted-foreground'}`}>
                              {EVENT_ICONS[event.event_type] || <Clock className="h-3 w-3" />}
                            </div>
                            <div className="flex-1">
                              <div className="font-medium">
                                {formatEventDescription(event)}
                              </div>
                              <div className="text-muted-foreground">
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
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}