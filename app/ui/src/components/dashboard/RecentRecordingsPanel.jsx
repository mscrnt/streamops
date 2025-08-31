import { MoreVertical, RefreshCw, FileVideo, FolderOpen, ExternalLink, Film } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Button from '@/components/ui/Button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAssets } from '@/hooks/useAssets'
import { Link, useNavigate } from 'react-router-dom'
import { formatBytes, formatDuration } from '@/lib/utils'

export default function RecentRecordingsPanel() {
  const navigate = useNavigate()
  
  // Use role-based filtering with override to ignore store filters
  const { data, isLoading, refetch } = useAssets(
    {
      role: 'recording',
      sort: 'created_at:desc',
      per_page: 10,
    },
    { override: true } // Do not merge with store defaults
  )
  
  const recordings = data?.assets || []
  
  // Extract drive letter from filepath
  const getDriveLetter = (filepath) => {
    if (!filepath) return null
    const match = filepath.match(/\/mnt\/drive_([a-z])\//i)
    if (match) {
      return match[1].toUpperCase()
    }
    return null
  }
  
  const getQualityBadge = (asset) => {
    if (!asset.metadata) return null
    const height = asset.metadata.height
    if (height >= 2160) return '4K'
    if (height >= 1440) return '2K'
    if (height >= 1080) return 'HD'
    if (height >= 720) return 'HD'
    return 'SD'
  }
  
  const getCodecLine = (asset) => {
    if (!asset.metadata) return null
    const parts = []
    
    if (asset.metadata.video_codec) {
      parts.push(asset.metadata.video_codec)
    }
    if (asset.metadata.frame_rate) {
      parts.push(`${Math.round(asset.metadata.frame_rate)}fps`)
    }
    if (asset.metadata.video_bitrate) {
      const mbps = (asset.metadata.video_bitrate / 1_000_000).toFixed(1)
      parts.push(`@ ${mbps}Mbps`)
    }
    
    return parts.length > 0 ? parts.join(' ') : null
  }
  
  const handleOpen = (asset) => {
    navigate(`/assets/${asset.id}`)
  }
  
  const handleLocate = (asset) => {
    navigate(`/assets?search=${encodeURIComponent(asset.filename)}`)
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
          <Link to="/assets?filter=recording&sort=created_at:desc">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Content with internal scroll */}
      <div className="h-[360px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-pulse text-sm text-muted-foreground">Loading recordings...</div>
          </div>
        ) : recordings.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <Film className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              No recent recordings from watched folders.
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {recordings.map((asset) => (
              <div
                key={asset.id}
                className="flex items-center gap-3 px-4 py-2 hover:bg-muted/30 cursor-pointer group"
                onClick={() => handleOpen(asset)}
              >
                <FileVideo className="h-4 w-4 text-muted-foreground flex-shrink-0" />
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate" title={asset.filepath}>
                      {asset.filename}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2 mt-1 flex-wrap">
                    {/* Badges */}
                    <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                      Recording
                    </span>
                    
                    {getDriveLetter(asset.filepath) && (
                      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-purple-100 text-purple-700 dark:bg-purple-950/50 dark:text-purple-300">
                        Drive {getDriveLetter(asset.filepath)}
                      </span>
                    )}
                    
                    {getQualityBadge(asset) && (
                      <span className="inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium bg-muted text-muted-foreground">
                        {getQualityBadge(asset)}
                      </span>
                    )}
                    
                    {asset.metadata?.duration && (
                      <span className="text-xs text-muted-foreground">
                        {formatDuration(asset.metadata.duration)}
                      </span>
                    )}
                    
                    {asset.metadata?.size_bytes && (
                      <span className="text-xs text-muted-foreground">
                        {formatBytes(asset.metadata.size_bytes)}
                      </span>
                    )}
                    
                    <span className="text-xs text-muted-foreground">
                      • {formatDistanceToNow(new Date(asset.created_at), { addSuffix: true })}
                    </span>
                  </div>
                  
                  {getCodecLine(asset) && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {getCodecLine(asset)}
                    </div>
                  )}
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
            ))}
          </div>
        )}
      </div>
    </div>
  )
}