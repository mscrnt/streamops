import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  X, Download, Archive, Trash2, Copy, Move, Play, 
  RefreshCw, Tag, Clock, HardDrive, Film, Volume2,
  FileText, Loader2, CheckCircle, AlertCircle, ExternalLink,
  FileVideo, Package
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'
import { formatDistanceToNow } from 'date-fns'

export default function AssetPreviewDrawer({ assetId, onClose, onAction }) {
  const { api } = useApi()
  const [copiedPath, setCopiedPath] = useState(false)
  const [selectedTab, setSelectedTab] = useState('details')
  
  // Fetch asset details
  const { data: assetData, isLoading, error } = useQuery({
    queryKey: ['asset', assetId],
    queryFn: async () => {
      const response = await api.get(`/assets/${assetId}/detail`)
      return response.data
    },
    enabled: !!assetId
  })
  
  // Fetch timeline to get current file location
  const { data: timelineData } = useQuery({
    queryKey: ['asset-timeline', assetId],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${assetId}/timeline`)
      if (!res.ok) throw new Error('Failed to fetch timeline')
      return res.json()
    },
    enabled: !!assetId
  })
  
  // Fetch asset path
  const { data: pathData } = useQuery({
    queryKey: ['asset-path', assetId],
    queryFn: async () => {
      const response = await api.get(`/assets/${assetId}/path`)
      return response.data
    },
    enabled: !!assetId
  })
  
  const asset = assetData?.asset
  const thumbs = assetData?.thumbs
  const recentJobs = assetData?.jobs_recent || []
  const timeline = timelineData?.timeline || []
  
  // Get current file path from timeline (checking remux and move events)
  const getCurrentPath = () => {
    let path = asset?.abs_path || asset?.filepath
    
    if (timeline.length > 0) {
      // Process events chronologically to track file path changes
      // This ensures we follow the actual sequence: original -> remux -> move
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
  const currentFilename = currentPath ? currentPath.split('/').pop() : (asset?.name || 'Unknown')
  
  // Determine current container format based on file extension
  const getCurrentContainer = () => {
    if (!currentPath) return asset?.container
    const ext = currentPath.split('.').pop()?.toLowerCase()
    const containerMap = {
      'mp4': 'MP4',
      'mov': 'MOV',
      'mkv': 'MATROSKA',
      'webm': 'WEBM',
      'avi': 'AVI',
      'flv': 'FLV'
    }
    return containerMap[ext] || asset?.container
  }
  
  const handleCopyPath = () => {
    if (currentPath) {
      navigator.clipboard.writeText(currentPath)
      setCopiedPath(true)
      toast.success('Path copied to clipboard')
      setTimeout(() => setCopiedPath(false), 2000)
    }
  }
  
  const handleAction = (action) => {
    onAction(assetId, action)
  }
  
  // Close on escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])
  
  // Prevent body scroll when drawer is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])
  
  if (!assetId) return null
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[500px] bg-background border-l border-border shadow-xl z-50 flex flex-col">
        {/* Header */}
        <div className="border-b border-border p-4">
          <div className="flex items-center justify-between">
            <div className="flex-1 min-w-0">
              <h2 className="text-lg font-semibold truncate">
                {currentFilename}
              </h2>
              {currentPath && currentPath !== asset?.abs_path && (
                <p className="text-xs text-muted-foreground mt-1">
                  Updated location after {timeline.some(e => e.event_type === 'remux_completed') ? 'remux/move' : 'move'}
                </p>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="ml-2"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="flex items-center justify-center h-64">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="p-4">
              <Card className="border-destructive">
                <CardContent className="p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-destructive mt-0.5" />
                    <div>
                      <p className="font-medium">Failed to load asset</p>
                      <p className="text-sm text-muted-foreground mt-1">
                        {error.response?.data?.detail || error.message}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          ) : asset ? (
            <>
              {/* Preview */}
              <div className="aspect-video bg-muted relative group">
                {asset.video_codec ? (
                  <>
                    {/* Use native video element with controls */}
                    <video
                      className="w-full h-full object-contain"
                      src={`/api/assets/${assetId}/stream`}
                      controls
                      preload="metadata"
                      onLoadedMetadata={(e) => {
                        // Seek to 10% of the video for a representative frame
                        if (!e.target.hasAttribute('data-playing')) {
                          e.target.currentTime = Math.min(5, e.target.duration * 0.1 || 0)
                        }
                      }}
                      onPlay={(e) => {
                        e.target.setAttribute('data-playing', 'true')
                      }}
                      onPause={(e) => {
                        e.target.removeAttribute('data-playing')
                      }}
                    />
                  </>
                ) : (
                  <div className="absolute inset-0 flex items-center justify-center">
                    {asset.audio_codec ? (
                      <Volume2 className="w-12 h-12 text-muted-foreground" />
                    ) : (
                      <FileText className="w-12 h-12 text-muted-foreground" />
                    )}
                  </div>
                )}
              </div>
              
              {/* Quick Actions */}
              <div className="p-4 border-b border-border">
                <div className="grid grid-cols-3 gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('download')}
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('remux')}
                  >
                    <RefreshCw className="w-4 h-4 mr-2" />
                    Remux
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('proxy')}
                  >
                    <Film className="w-4 h-4 mr-2" />
                    Proxy
                  </Button>
                </div>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('thumbnails')}
                  >
                    <Film className="w-4 h-4 mr-2" />
                    Thumbs
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('archive')}
                  >
                    <Archive className="w-4 h-4 mr-2" />
                    Archive
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleAction('delete')}
                    className="text-destructive hover:text-destructive"
                  >
                    <Trash2 className="w-4 h-4 mr-2" />
                    Delete
                  </Button>
                </div>
              </div>
              
              {/* Tabs */}
              <div className="border-b border-border">
                <div className="flex">
                  <button
                    className={cn(
                      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                      selectedTab === 'details' 
                        ? "border-primary text-primary" 
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => setSelectedTab('details')}
                  >
                    Details
                  </button>
                  <button
                    className={cn(
                      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                      selectedTab === 'streams' 
                        ? "border-primary text-primary" 
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => setSelectedTab('streams')}
                  >
                    Streams
                  </button>
                  <button
                    className={cn(
                      "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                      selectedTab === 'jobs' 
                        ? "border-primary text-primary" 
                        : "border-transparent text-muted-foreground hover:text-foreground"
                    )}
                    onClick={() => setSelectedTab('jobs')}
                  >
                    Jobs ({recentJobs.length})
                  </button>
                </div>
              </div>
              
              {/* Tab Content */}
              <div className="p-4">
                {selectedTab === 'details' && (
                  <div className="space-y-4">
                    {/* File Info */}
                    <div>
                      <h3 className="text-sm font-medium mb-2">File Information</h3>
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Size</span>
                          <span className="font-medium">{formatBytes(asset.size)}</span>
                        </div>
                        {asset.duration_sec && (
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Duration</span>
                            <span className="font-medium">{formatDuration(asset.duration_sec)}</span>
                          </div>
                        )}
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Container</span>
                          <span className="font-medium">{getCurrentContainer()}</span>
                        </div>
                        {asset.width && asset.height && (
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Resolution</span>
                            <span className="font-medium">{asset.width}×{asset.height}</span>
                          </div>
                        )}
                        {asset.fps && (
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Frame Rate</span>
                            <span className="font-medium">{asset.fps} fps</span>
                          </div>
                        )}
                        {asset.video_codec && (
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Video Codec</span>
                            <span className="font-medium">{asset.video_codec}</span>
                          </div>
                        )}
                        {asset.audio_codec && (
                          <div className="flex justify-between text-sm">
                            <span className="text-muted-foreground">Audio Codec</span>
                            <span className="font-medium">{asset.audio_codec}</span>
                          </div>
                        )}
                      </div>
                    </div>
                    
                    {/* Path */}
                    <div>
                      <h3 className="text-sm font-medium mb-2">Current Location</h3>
                      <div className="space-y-2">
                        <div className="p-2 bg-muted rounded text-xs font-mono break-all">
                          {currentPath}
                        </div>
                        <div className="flex gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCopyPath}
                            className="flex-1"
                          >
                            {copiedPath ? (
                              <>
                                <CheckCircle className="w-4 h-4 mr-2 text-green-500" />
                                Copied!
                              </>
                            ) : (
                              <>
                                <Copy className="w-4 h-4 mr-2" />
                                Copy Path
                              </>
                            )}
                          </Button>
                          {pathData?.can_open_on_host && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                // Would open folder if supported
                                toast.info('Opening folder not yet supported')
                              }}
                            >
                              <ExternalLink className="w-4 h-4 mr-2" />
                              Open Folder
                            </Button>
                          )}
                        </div>
                        {pathData?.host_hint && (
                          <p className="text-xs text-muted-foreground">
                            This is your host path. Paste into Explorer/Finder to open the folder.
                          </p>
                        )}
                      </div>
                    </div>
                    
                    {/* Metadata */}
                    <div>
                      <h3 className="text-sm font-medium mb-2">Metadata</h3>
                      <div className="space-y-2">
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Status</span>
                          <Badge variant={
                            asset.status === 'completed' ? 'success' :
                            asset.status === 'pending' ? 'warning' :
                            asset.status === 'error' ? 'destructive' :
                            asset.status === 'processing' ? 'outline' :
                            'secondary'
                          }>
                            {asset.status}
                          </Badge>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Created</span>
                          <span className="font-medium">{formatRelativeTime(asset.created_at)}</span>
                        </div>
                        <div className="flex justify-between text-sm">
                          <span className="text-muted-foreground">Updated</span>
                          <span className="font-medium">{formatRelativeTime(asset.updated_at)}</span>
                        </div>
                      </div>
                    </div>
                    
                    {/* Tags */}
                    {asset.tags && asset.tags.length > 0 && (
                      <div>
                        <h3 className="text-sm font-medium mb-2">Tags</h3>
                        <div className="flex flex-wrap gap-2">
                          {asset.tags.map(tag => (
                            <Badge key={tag} variant="outline">
                              <Tag className="w-3 h-3 mr-1" />
                              {tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
                
                {selectedTab === 'streams' && (
                  <div className="space-y-4">
                    {asset.streams && asset.streams.length > 0 ? (
                      asset.streams.map((stream, index) => (
                        <Card key={index}>
                          <CardContent className="p-3">
                            <div className="flex items-center justify-between mb-2">
                              <Badge variant="outline">
                                Stream #{stream.index || index}
                              </Badge>
                              <Badge>
                                {stream.codec_type}
                              </Badge>
                            </div>
                            <div className="space-y-1 text-sm">
                              <div className="flex justify-between">
                                <span className="text-muted-foreground">Codec</span>
                                <span>{stream.codec_name}</span>
                              </div>
                              {stream.width && stream.height && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Resolution</span>
                                  <span>{stream.width}×{stream.height}</span>
                                </div>
                              )}
                              {stream.bit_rate && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Bitrate</span>
                                  <span>{formatBytes(parseInt(stream.bit_rate))}ps</span>
                                </div>
                              )}
                              {stream.channels && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Channels</span>
                                  <span>{stream.channels}</span>
                                </div>
                              )}
                              {stream.sample_rate && (
                                <div className="flex justify-between">
                                  <span className="text-muted-foreground">Sample Rate</span>
                                  <span>{stream.sample_rate} Hz</span>
                                </div>
                              )}
                            </div>
                          </CardContent>
                        </Card>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-8">
                        No stream information available
                      </p>
                    )}
                  </div>
                )}
                
                {selectedTab === 'jobs' && (
                  <div className="space-y-2">
                    {recentJobs.length > 0 ? (
                      recentJobs.map(job => (
                        <Card key={job.id}>
                          <CardContent className="p-3">
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <Badge variant={
                                  job.state === 'completed' ? 'success' :
                                  job.state === 'failed' ? 'destructive' :
                                  job.state === 'running' ? 'warning' :
                                  'secondary'
                                }>
                                  {job.state}
                                </Badge>
                                <span className="text-sm font-medium">{job.type}</span>
                              </div>
                              {job.duration_sec && (
                                <span className="text-sm text-muted-foreground">
                                  {formatDuration(job.duration_sec)}
                                </span>
                              )}
                            </div>
                            {job.ended_at && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {formatRelativeTime(job.ended_at)}
                              </p>
                            )}
                          </CardContent>
                        </Card>
                      ))
                    ) : (
                      <p className="text-sm text-muted-foreground text-center py-8">
                        No recent jobs for this asset
                      </p>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </>
  )
}