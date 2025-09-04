import { useState, useEffect } from 'react'
import { X, Loader2, AlertCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import VideoPlayer from './VideoPlayer'
import { cn } from '@/lib/utils'
import Button from '@/components/ui/Button'

export default function VideoPlayerModal({ assetId, onClose }) {
  const [error, setError] = useState(null)
  
  // Fetch asset details and timeline to get current path
  const { data: assetData, isLoading: assetLoading } = useQuery({
    queryKey: ['asset', assetId],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${assetId}/detail`)
      if (!res.ok) throw new Error('Failed to fetch asset')
      return res.json()
    },
    enabled: !!assetId
  })
  
  // Check stream info for proxy status
  const { data: streamInfo } = useQuery({
    queryKey: ['asset-stream', assetId],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${assetId}/stream-info`)
      if (!res.ok) throw new Error('Cannot check stream info')
      return res.json()
    },
    enabled: !!assetId
  })
  
  const { data: timelineData } = useQuery({
    queryKey: ['asset-timeline', assetId],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${assetId}/timeline`)
      if (!res.ok) throw new Error('Failed to fetch timeline')
      return res.json()
    },
    enabled: !!assetId
  })
  
  // Get current file path from timeline
  const getCurrentPath = () => {
    const timeline = timelineData?.timeline || []
    let path = assetData?.asset?.abs_path || assetData?.asset?.filepath
    
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
  const filename = currentPath?.split('/').pop() || 'Video'
  
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
  
  // Prevent body scroll when modal is open
  useEffect(() => {
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = 'unset'
    }
  }, [])
  
  if (assetLoading) {
    return (
      <>
        <div className="fixed inset-0 bg-black/80 z-50" onClick={onClose} />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg p-8">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        </div>
      </>
    )
  }
  
  if (error || !assetData) {
    return (
      <>
        <div className="fixed inset-0 bg-black/80 z-50" onClick={onClose} />
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="bg-background rounded-lg p-8 max-w-md">
            <div className="flex items-center gap-3 text-destructive mb-4">
              <AlertCircle className="h-6 w-6" />
              <span className="font-medium">Unable to load video</span>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              {error?.message || 'Failed to load asset information'}
            </p>
            <Button onClick={onClose}>Close</Button>
          </div>
        </div>
      </>
    )
  }
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/90 z-50"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div className="bg-background rounded-lg shadow-2xl w-full max-w-5xl pointer-events-auto">
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold truncate">
                  {filename}
                </h2>
                {streamInfo?.using_proxy && (
                  <span className="px-2 py-0.5 bg-blue-500/20 text-blue-600 dark:text-blue-400 text-xs rounded">
                    Using Proxy
                  </span>
                )}
              </div>
              <p className="text-xs text-muted-foreground mt-1 truncate">
                {currentPath}
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
              className="flex-shrink-0 ml-4"
            >
              <X className="h-5 w-5" />
            </Button>
          </div>
          
          {/* Video Player */}
          <div className="p-4">
            <VideoPlayer assetId={assetId} currentPath={currentPath} />
            
            {/* Asset info */}
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {assetData.asset.duration_sec && (
                <div>
                  <span className="text-muted-foreground">Duration: </span>
                  <span className="font-medium">
                    {Math.floor(assetData.asset.duration_sec / 60)}:
                    {String(Math.floor(assetData.asset.duration_sec % 60)).padStart(2, '0')}
                  </span>
                </div>
              )}
              {assetData.asset.width && assetData.asset.height && (
                <div>
                  <span className="text-muted-foreground">Resolution: </span>
                  <span className="font-medium">
                    {assetData.asset.width}×{assetData.asset.height}
                  </span>
                </div>
              )}
              {assetData.asset.video_codec && (
                <div>
                  <span className="text-muted-foreground">Codec: </span>
                  <span className="font-medium">{assetData.asset.video_codec}</span>
                </div>
              )}
              {assetData.asset.fps && (
                <div>
                  <span className="text-muted-foreground">FPS: </span>
                  <span className="font-medium">{assetData.asset.fps}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}