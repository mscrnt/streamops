import { useState, useEffect } from 'react'
import { 
  Layers, 
  Monitor,
  Copy,
  Check,
  Info,
  Eye,
  EyeOff
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { SimpleSelect } from '@/components/ui/Select'
import Input from '@/components/ui/Input'
import toast from 'react-hot-toast'

export default function WizardOverlays({ data = {}, onChange, defaults }) {
  const [overlayConfig, setOverlayConfig] = useState({
    enabled: data.enabled || false,
    preset: data.preset || '',
    position: data.position || 'bottom-right',
    margin: data.margin || 20
  })
  
  const [copied, setCopied] = useState(false)
  
  // Notify parent of changes
  useEffect(() => {
    if (!onChange) return
    onChange(overlayConfig)
  }, [overlayConfig]) // Intentionally omit onChange to prevent loops
  
  const handleToggle = () => {
    setOverlayConfig(prev => ({ ...prev, enabled: !prev.enabled }))
  }
  
  const handlePresetChange = (preset) => {
    setOverlayConfig(prev => ({ ...prev, preset }))
  }
  
  const handlePositionChange = (position) => {
    setOverlayConfig(prev => ({ ...prev, position }))
  }
  
  const handleMarginChange = (e) => {
    setOverlayConfig(prev => ({ ...prev, margin: parseInt(e.target.value) }))
  }
  
  const copyOverlayUrl = () => {
    const url = `http://localhost:7767/overlay/${overlayConfig.preset || 'sponsor'}`
    navigator.clipboard.writeText(url)
    setCopied(true)
    toast.success('Overlay URL copied to clipboard')
    setTimeout(() => setCopied(false), 2000)
  }
  
  const presets = defaults?.overlay_presets || []
  
  return (
    <div className="space-y-6">
      {/* Enable/Disable */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Stream Overlays
            <Button
              variant={overlayConfig.enabled ? 'default' : 'outline'}
              onClick={handleToggle}
            >
              {overlayConfig.enabled ? (
                <>
                  <Eye className="h-4 w-4 mr-2" />
                  Enabled
                </>
              ) : (
                <>
                  <EyeOff className="h-4 w-4 mr-2" />
                  Disabled
                </>
              )}
            </Button>
          </CardTitle>
          <CardDescription>
            Add dynamic overlays to your stream with Browser Source in OBS
          </CardDescription>
        </CardHeader>
      </Card>
      
      {/* Preset Selection */}
      {overlayConfig.enabled && (
        <>
          <Card>
            <CardHeader>
              <CardTitle>Choose Overlay Preset</CardTitle>
              <CardDescription>
                Select a pre-built overlay template to get started quickly
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {presets.map(preset => (
                  <Card 
                    key={preset.id}
                    className={`cursor-pointer transition-all ${
                      overlayConfig.preset === preset.id 
                        ? 'border-primary ring-2 ring-primary/20' 
                        : 'hover:border-primary/50'
                    }`}
                    onClick={() => handlePresetChange(preset.id)}
                  >
                    <CardHeader>
                      <CardTitle className="text-base flex items-center justify-between">
                        {preset.label}
                        {overlayConfig.preset === preset.id && (
                          <Check className="h-5 w-5 text-primary" />
                        )}
                      </CardTitle>
                      <CardDescription>
                        {preset.description}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
          
          {/* Configuration */}
          {overlayConfig.preset && (
            <Card>
              <CardHeader>
                <CardTitle>Overlay Settings</CardTitle>
                <CardDescription>
                  Configure position and appearance
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Position
                    </label>
                    <SimpleSelect
                      value={overlayConfig.position}
                      onChange={handlePositionChange}
                      className="w-full"
                    >
                      <option value="top-left">Top Left</option>
                      <option value="top-right">Top Right</option>
                      <option value="bottom-left">Bottom Left</option>
                      <option value="bottom-right">Bottom Right</option>
                      <option value="top">Top Center</option>
                      <option value="bottom">Bottom Center</option>
                    </SimpleSelect>
                  </div>
                  
                  <div>
                    <label className="text-sm font-medium mb-2 block">
                      Margin (pixels)
                    </label>
                    <Input
                      type="number"
                      value={overlayConfig.margin}
                      onChange={handleMarginChange}
                      min="0"
                      max="100"
                      className="w-full"
                    />
                  </div>
                </div>
                
                {/* Preview */}
                <div className="p-4 bg-muted rounded-lg">
                  <div className="aspect-video bg-background rounded-lg relative">
                    <div className="absolute inset-0 flex items-center justify-center text-muted-foreground">
                      <Monitor className="h-12 w-12" />
                    </div>
                    
                    {/* Show overlay position */}
                    <div 
                      className={`absolute ${
                        overlayConfig.position.includes('top') ? 'top-4' : ''
                      } ${
                        overlayConfig.position.includes('bottom') ? 'bottom-4' : ''
                      } ${
                        overlayConfig.position.includes('left') ? 'left-4' : ''
                      } ${
                        overlayConfig.position.includes('right') ? 'right-4' : ''
                      } ${
                        overlayConfig.position === 'top' ? 'left-1/2 -translate-x-1/2' : ''
                      } ${
                        overlayConfig.position === 'bottom' ? 'left-1/2 -translate-x-1/2' : ''
                      }`}
                      style={{ 
                        margin: `${overlayConfig.margin}px`
                      }}
                    >
                      <div className="bg-primary/20 border-2 border-primary rounded-lg p-3">
                        <Layers className="h-6 w-6 text-primary" />
                      </div>
                    </div>
                  </div>
                  <p className="text-xs text-muted-foreground text-center mt-2">
                    Preview of overlay position
                  </p>
                </div>
                
                {/* OBS Setup */}
                <div className="border rounded-lg p-4 space-y-3">
                  <h4 className="font-medium">Add to OBS</h4>
                  <ol className="space-y-2 text-sm text-muted-foreground">
                    <li>1. In OBS, add a Browser Source to your scene</li>
                    <li>2. Set the URL to:</li>
                  </ol>
                  <div className="flex items-center space-x-2">
                    <code className="flex-1 p-2 bg-muted rounded font-mono text-xs">
                      http://localhost:7767/overlay/{overlayConfig.preset}
                    </code>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={copyOverlayUrl}
                    >
                      {copied ? (
                        <Check className="h-4 w-4" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                  <ol className="space-y-2 text-sm text-muted-foreground" start={3}>
                    <li>3. Set Width: 1920, Height: 1080</li>
                    <li>4. Check "Shutdown source when not visible"</li>
                  </ol>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
      
      {/* Info */}
      <Card className="border-blue-500/50 bg-blue-500/10">
        <CardContent className="py-4">
          <div className="flex items-start space-x-3">
            <Info className="h-5 w-5 text-blue-500 mt-0.5" />
            <div>
              <p className="font-medium">Overlays are Optional</p>
              <p className="text-sm text-muted-foreground">
                You can skip this step and add overlays later. StreamOps will work perfectly without them.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}