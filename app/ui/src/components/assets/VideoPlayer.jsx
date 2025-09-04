import { useEffect, useRef, useState } from 'react'
import Plyr from 'plyr'
import 'plyr/dist/plyr.css'
import { Loader2, AlertCircle } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'

export default function VideoPlayer({ assetId, currentPath }) {
  const videoRef = useRef(null)
  const playerRef = useRef(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  
  // Generate the video URL - API should serve the file from its current location
  const videoUrl = `/api/assets/${assetId}/stream`
  
  // Check if video is accessible
  const { data: streamInfo } = useQuery({
    queryKey: ['asset-stream', assetId],
    queryFn: async () => {
      const res = await fetch(`/api/assets/${assetId}/stream-info`)
      if (!res.ok) {
        throw new Error('Cannot access video')
      }
      return res.json()
    },
    onError: (err) => {
      setError(err.message)
      setLoading(false)
    }
  })
  
  useEffect(() => {
    if (!videoRef.current || playerRef.current) return
    
    // Initialize Plyr player
    playerRef.current = new Plyr(videoRef.current, {
      controls: [
        'play-large',
        'play',
        'progress',
        'current-time',
        'duration',
        'mute',
        'volume',
        'captions',
        'settings',
        'pip',
        'airplay',
        'fullscreen'
      ],
      settings: ['captions', 'quality', 'speed', 'loop'],
      speed: { selected: 1, options: [0.5, 0.75, 1, 1.25, 1.5, 2] },
      keyboard: { focused: true, global: false },
      tooltips: { controls: true, seek: true },
      hideControls: true,
      displayDuration: true,
      invertTime: false,
      fullscreen: { enabled: true, fallback: true, iosNative: false }
    })
    
    // Handle player events
    playerRef.current.on('ready', () => {
      setLoading(false)
    })
    
    playerRef.current.on('error', (event) => {
      console.error('Plyr error:', event.detail)
      setError('Failed to load video')
      setLoading(false)
    })
    
    return () => {
      if (playerRef.current) {
        playerRef.current.destroy()
        playerRef.current = null
      }
    }
  }, [videoRef.current])
  
  if (error) {
    return (
      <div className="aspect-video bg-black rounded-lg flex items-center justify-center">
        <div className="text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-2" />
          <p className="text-white">{error}</p>
          {currentPath && (
            <p className="text-xs text-gray-400 mt-2">
              File location: {currentPath}
            </p>
          )}
        </div>
      </div>
    )
  }
  
  return (
    <div className="relative aspect-video bg-black rounded-lg overflow-hidden">
      {loading && (
        <div className="absolute inset-0 flex items-center justify-center z-10">
          <Loader2 className="h-8 w-8 animate-spin text-white" />
        </div>
      )}
      
      {streamInfo?.using_proxy && (
        <div className="absolute top-2 left-2 z-20 px-2 py-1 bg-blue-500/80 text-white text-xs rounded">
          Proxy
        </div>
      )}
      
      <video
        ref={videoRef}
        className="w-full h-full"
        crossOrigin="anonymous"
        playsInline
        controls
      >
        <source src={videoUrl} type="video/mp4" />
        <source src={videoUrl} type="video/webm" />
        <source src={videoUrl} type="video/ogg" />
        Your browser does not support the video tag.
      </video>
    </div>
  )
}