import { useState, useEffect } from 'react'
import { 
  X, AlertTriangle, Archive, Trash2, Move, RefreshCw,
  Play, Info, CheckCircle, FolderOpen, HardDrive
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import { formatBytes } from '@/lib/utils'

export default function AssetActionModal({ 
  action, 
  assetId, 
  bulk = false, 
  selectedCount = 1,
  onConfirm, 
  onClose 
}) {
  const [params, setParams] = useState({})
  const [isConfirming, setIsConfirming] = useState(false)
  
  // Set default params based on action
  useEffect(() => {
    switch (action) {
      case 'remux':
        setParams({ container: 'mov', faststart: true })
        break
      case 'proxy':
        setParams({ resolution: '1080p' })
        break
      case 'delete':
        setParams({ to_trash: true })
        break
      case 'archive':
        setParams({ policy: 'default' })
        break
      case 'move':
        setParams({ dest: '' })
        break
      default:
        setParams({})
    }
  }, [action])
  
  const handleConfirm = () => {
    setIsConfirming(true)
    onConfirm(params)
  }
  
  // Action configurations
  const actionConfig = {
    remux: {
      title: 'Remux Asset',
      icon: RefreshCw,
      description: 'Convert container format while preserving quality',
      variant: 'default'
    },
    proxy: {
      title: 'Create Proxy',
      icon: Play,
      description: 'Generate lightweight proxy for smooth editing',
      variant: 'default'
    },
    thumbnails: {
      title: 'Generate Thumbnails',
      icon: Play,
      description: 'Create poster, sprite sheet, and hover preview',
      variant: 'default'
    },
    move: {
      title: 'Move Asset',
      icon: Move,
      description: 'Move to a different location',
      variant: 'default'
    },
    archive: {
      title: 'Archive Asset',
      icon: Archive,
      description: 'Move to archive storage and tag as archived',
      variant: 'warning'
    },
    delete: {
      title: 'Delete Asset',
      icon: Trash2,
      description: 'Remove asset from system',
      variant: 'destructive'
    },
    reindex: {
      title: 'Reindex Asset',
      icon: RefreshCw,
      description: 'Re-scan and update metadata',
      variant: 'default'
    }
  }
  
  const config = actionConfig[action] || {}
  const Icon = config.icon || Info
  
  // Close on escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && !isConfirming) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose, isConfirming])
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        <Card className="w-full max-w-md">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={cn(
                  "p-2 rounded-lg",
                  config.variant === 'destructive' ? 'bg-destructive/10 text-destructive' :
                  config.variant === 'warning' ? 'bg-yellow-500/10 text-yellow-600' :
                  'bg-primary/10 text-primary'
                )}>
                  <Icon className="w-5 h-5" />
                </div>
                <div>
                  <CardTitle>{config.title}</CardTitle>
                  {bulk && (
                    <CardDescription className="mt-1">
                      {selectedCount} {selectedCount === 1 ? 'asset' : 'assets'} selected
                    </CardDescription>
                  )}
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                disabled={isConfirming}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </CardHeader>
          
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {config.description}
            </p>
            
            {/* Action-specific options */}
            {action === 'remux' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Container Format
                  </label>
                  <select
                    value={params.container}
                    onChange={(e) => setParams({ ...params, container: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-lg bg-background"
                  >
                    <option value="mp4">MP4</option>
                    <option value="mov">MOV</option>
                    <option value="mkv">MKV</option>
                    <option value="webm">WebM</option>
                  </select>
                  <p className="text-xs text-muted-foreground mt-1">
                    MOV recommended for editing, MP4 for web delivery
                  </p>
                </div>
                
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="faststart"
                    checked={params.faststart}
                    onChange={(e) => setParams({ ...params, faststart: e.target.checked })}
                    className="rounded border-input"
                  />
                  <label htmlFor="faststart" className="text-sm">
                    Enable fast start (recommended for web)
                  </label>
                </div>
                
                <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                  <p className="text-sm text-primary">
                    <Info className="w-4 h-4 inline mr-2" />
                    Remuxing preserves original quality - no re-encoding
                  </p>
                </div>
              </div>
            )}
            
            {action === 'proxy' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Proxy Resolution
                  </label>
                  <select
                    value={params.resolution}
                    onChange={(e) => setParams({ ...params, resolution: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-lg bg-background"
                  >
                    <option value="720p">720p (HD)</option>
                    <option value="1080p">1080p (Full HD)</option>
                    <option value="1440p">1440p (2K)</option>
                    <option value="2160p">2160p (4K)</option>
                  </select>
                  <p className="text-xs text-muted-foreground mt-1">
                    Lower resolution = faster editing, smaller file size
                  </p>
                </div>
                
                <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                  <p className="text-sm text-primary">
                    <Info className="w-4 h-4 inline mr-2" />
                    Proxies are lightweight copies used for smooth editing. Final export uses your originals.
                  </p>
                </div>
                
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Codec</span>
                    <span>DNxHR LB (720p/1080p) or DNxHR SQ (higher)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Estimated Size</span>
                    <span>~10-20% of original</span>
                  </div>
                </div>
              </div>
            )}
            
            {action === 'move' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Destination Folder
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={params.dest}
                      onChange={(e) => setParams({ ...params, dest: e.target.value })}
                      placeholder="/mnt/drive_f/Editing/{date}/"
                      className="flex-1 px-3 py-2 border border-input rounded-lg bg-background"
                    />
                    <Button variant="outline" size="icon">
                      <FolderOpen className="w-4 h-4" />
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Use {'{date}'} for auto date folders (YYYY-MM-DD)
                  </p>
                </div>
                
                <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                  <p className="text-sm text-yellow-600 dark:text-yellow-400">
                    <AlertTriangle className="w-4 h-4 inline mr-2" />
                    Files will be moved, not copied. Original location will be updated.
                  </p>
                </div>
              </div>
            )}
            
            {action === 'archive' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">
                    Archive Policy
                  </label>
                  <select
                    value={params.policy}
                    onChange={(e) => setParams({ ...params, policy: e.target.value })}
                    className="w-full px-3 py-2 border border-input rounded-lg bg-background"
                  >
                    <option value="default">Default Archive Location</option>
                    <option value="compress">Compress & Archive</option>
                    <option value="cold">Cold Storage</option>
                  </select>
                </div>
                
                <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                  <p className="text-sm text-primary">
                    <Info className="w-4 h-4 inline mr-2" />
                    Archives move files to your archive drive and tag them 'archived'. You can restore anytime.
                  </p>
                </div>
                
                <div className="flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">
                    Archive location: /mnt/archive/
                  </span>
                </div>
              </div>
            )}
            
            {action === 'delete' && (
              <div className="space-y-4">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="to_trash"
                    checked={params.to_trash}
                    onChange={(e) => setParams({ ...params, to_trash: e.target.checked })}
                    className="rounded border-input"
                  />
                  <label htmlFor="to_trash" className="text-sm">
                    Move to trash (can be restored)
                  </label>
                </div>
                
                {!params.to_trash && (
                  <div className="p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                    <p className="text-sm text-destructive">
                      <AlertTriangle className="w-4 h-4 inline mr-2" />
                      Permanent deletion cannot be undone!
                    </p>
                  </div>
                )}
                
                {bulk && (
                  <div className="p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
                    <p className="text-sm text-yellow-600 dark:text-yellow-400">
                      <AlertTriangle className="w-4 h-4 inline mr-2" />
                      This will delete {selectedCount} {selectedCount === 1 ? 'asset' : 'assets'}
                    </p>
                  </div>
                )}
              </div>
            )}
            
            {action === 'thumbnails' && (
              <div className="space-y-4">
                <div className="p-3 bg-primary/10 border border-primary/20 rounded-lg">
                  <p className="text-sm text-primary">
                    <Info className="w-4 h-4 inline mr-2" />
                    Will generate poster image, sprite sheet, and hover preview video
                  </p>
                </div>
                
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span>Poster image at 10% duration</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span>3x3 sprite sheet for timeline scrubbing</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500" />
                    <span>10-second hover preview video</span>
                  </div>
                </div>
              </div>
            )}
            
            {/* Action buttons */}
            <div className="flex gap-2 pt-2">
              <Button
                variant="outline"
                onClick={onClose}
                disabled={isConfirming}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant={config.variant === 'destructive' ? 'destructive' : 'default'}
                onClick={handleConfirm}
                disabled={isConfirming}
                loading={isConfirming}
                className="flex-1"
              >
                {isConfirming ? 'Processing...' : 'Confirm'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}