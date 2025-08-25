import { useNavigate } from 'react-router-dom'
import { 
  FileVideo, 
  Film, 
  Image as ImageIcon, 
  Music, 
  File,
  Play,
  Eye,
  Download,
  MoreVertical,
  ChevronRight,
  Clock,
  HardDrive,
  Tag
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'

export default function RecentAssetsList({ assets, loading, onViewAll }) {
  const navigate = useNavigate()
  
  // Get icon based on media type
  const getAssetIcon = (asset) => {
    if (asset.asset_type === 'video') return FileVideo
    if (asset.asset_type === 'audio') return Music
    if (asset.asset_type === 'image') return ImageIcon
    if (asset.filename?.endsWith('.edl') || asset.filename?.endsWith('.xml')) return Film
    return File
  }
  
  // Format codec info
  const formatCodec = (asset) => {
    const codecs = []
    const metadata = asset.metadata || {}
    if (metadata.codec) {
      const resolution = metadata.height ? `${metadata.height}p` : ''
      const fps = metadata.fps ? `@${Math.round(metadata.fps)}fps` : ''
      codecs.push(`${metadata.codec} ${resolution}${fps}`)
    }
    return codecs.join(', ')
  }
  
  // Get quality badge color
  const getQualityVariant = (asset) => {
    const height = asset.metadata?.height || 0
    if (height >= 2160) return 'destructive' // 4K
    if (height >= 1440) return 'warning' // 2K
    if (height >= 1080) return 'primary' // 1080p
    return 'secondary' // SD
  }
  
  // Get quality label
  const getQualityLabel = (asset) => {
    const height = asset.metadata?.height
    if (!height) return null
    if (height >= 2160) return '4K'
    if (height >= 1440) return '2K'
    if (height >= 1080) return 'FHD'
    if (height >= 720) return 'HD'
    return 'SD'
  }
  
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Recent Assets</CardTitle>
          <CardDescription>Latest media files processed</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-20 bg-muted animate-pulse rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Recent Assets</CardTitle>
            <CardDescription>
              {assets && assets.length > 0 
                ? `${assets.length} assets in the last 24 hours`
                : 'No recent assets'}
            </CardDescription>
          </div>
          {assets && assets.length > 0 && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={onViewAll}
            >
              View All
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {assets && assets.length > 0 ? (
          <div className="space-y-3">
            {assets.map((asset) => {
              const Icon = getAssetIcon(asset)
              const qualityLabel = getQualityLabel(asset)
              const codecInfo = formatCodec(asset)
              
              return (
                <div 
                  key={asset.id}
                  className="flex items-start space-x-3 p-3 rounded-lg border bg-card hover:bg-accent/50 cursor-pointer transition-colors"
                  onClick={() => navigate(`/assets/${asset.id}`)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      navigate(`/assets/${asset.id}`)
                    }
                  }}
                >
                  {/* Thumbnail or Icon */}
                  <div className="flex-shrink-0 w-20 h-12 bg-secondary rounded overflow-hidden">
                    {asset.poster_path ? (
                      <img 
                        src={`/api/assets/${asset.id}/poster`}
                        alt={asset.filename}
                        className="w-full h-full object-cover"
                        loading="lazy"
                      />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center">
                        <Icon className="h-6 w-6 text-muted-foreground" />
                      </div>
                    )}
                  </div>
                  
                  {/* Asset Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between mb-1">
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate" title={asset.filename}>
                          {asset.filename}
                        </p>
                        <div className="flex items-center space-x-2 mt-1">
                          {qualityLabel && (
                            <Badge variant={getQualityVariant(asset)} className="text-xs">
                              {qualityLabel}
                            </Badge>
                          )}
                          {asset.metadata?.duration && (
                            <span className="text-xs text-muted-foreground">
                              <Clock className="inline h-3 w-3 mr-1" />
                              {formatDuration(0, asset.metadata.duration * 1000)}
                            </span>
                          )}
                          {asset.metadata?.size_bytes && (
                            <span className="text-xs text-muted-foreground">
                              <HardDrive className="inline h-3 w-3 mr-1" />
                              {formatBytes(asset.metadata.size_bytes)}
                            </span>
                          )}
                          {asset.status === 'pending' && (
                            <Badge variant="outline" className="text-xs">
                              Pending
                            </Badge>
                          )}
                        </div>
                      </div>
                      
                      {/* Actions */}
                      <div className="flex items-center space-x-1 ml-2">
                        {asset.streamable && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={(e) => {
                              e.stopPropagation()
                              navigate(`/assets/${asset.id}/play`)
                            }}
                            aria-label="Play asset"
                          >
                            <Play className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={(e) => {
                            e.stopPropagation()
                            navigate(`/assets/${asset.id}`)
                          }}
                          aria-label="View details"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                    
                    {/* Additional Info */}
                    <div className="space-y-1">
                      {codecInfo && (
                        <p className="text-xs text-muted-foreground">
                          {codecInfo}
                        </p>
                      )}
                      
                      <div className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          {asset.tags && asset.tags.length > 0 && (
                            <div className="flex items-center space-x-1">
                              <Tag className="h-3 w-3 text-muted-foreground" />
                              {asset.tags.slice(0, 3).map(tag => (
                                <Badge key={tag} variant="outline" className="text-xs">
                                  {tag}
                                </Badge>
                              ))}
                              {asset.tags.length > 3 && (
                                <span className="text-xs text-muted-foreground">
                                  +{asset.tags.length - 3}
                                </span>
                              )}
                            </div>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground">
                          {formatRelativeTime(asset.created_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="text-center py-12">
            <FileVideo className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Recent Assets</h3>
            <p className="text-muted-foreground text-sm mb-4">
              Media files will appear here after they're recorded and processed.
            </p>
            <Button 
              variant="outline"
              onClick={() => navigate('/drives')}
            >
              Configure Drives
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  )
}