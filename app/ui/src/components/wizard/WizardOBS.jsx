import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { 
  Video, 
  Check, 
  X, 
  AlertCircle,
  Wifi,
  WifiOff,
  Eye,
  EyeOff,
  TestTube
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'

export default function WizardOBS({ data = {}, onChange, defaults }) {
  const { api } = useApi()
  const [obsConfig, setObsConfig] = useState({
    enabled: data.enabled || false,
    url: data.url || defaults?.obs_url || 'ws://host.docker.internal:4455',
    password: data.password || ''
  })
  const [showPassword, setShowPassword] = useState(false)
  const [testResult, setTestResult] = useState(null)
  
  // Test OBS connection
  const testMutation = useMutation({
    mutationFn: async ({ url, password }) => {
      const response = await api.post('/system/probe-obs', { url, password })
      return response.data
    },
    onSuccess: (data) => {
      setTestResult(data)
      if (data.ok) {
        // Auto-enable if connection successful
        const updated = { ...obsConfig, enabled: true }
        setObsConfig(updated)
        onChange(updated)
      }
    },
    onError: (error) => {
      setTestResult({
        ok: false,
        reason: error.message || 'Connection failed'
      })
    }
  })
  
  const handleToggleOBS = () => {
    const updated = { ...obsConfig, enabled: !obsConfig.enabled }
    setObsConfig(updated)
    onChange(updated)
  }
  
  const handleUrlChange = (e) => {
    const updated = { ...obsConfig, url: e.target.value }
    setObsConfig(updated)
    onChange(updated)
    setTestResult(null) // Clear test result on change
  }
  
  const handlePasswordChange = (e) => {
    const updated = { ...obsConfig, password: e.target.value }
    setObsConfig(updated)
    onChange(updated)
    setTestResult(null) // Clear test result on change
  }
  
  const handleTest = () => {
    testMutation.mutate({
      url: obsConfig.url,
      password: obsConfig.password
    })
  }
  
  const canTest = obsConfig.url && obsConfig.password
  
  return (
    <div className="space-y-6">
      {/* Enable/Disable Toggle */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            OBS WebSocket Integration
            <Button
              variant={obsConfig.enabled ? 'default' : 'outline'}
              onClick={handleToggleOBS}
            >
              {obsConfig.enabled ? (
                <>
                  <Wifi className="h-4 w-4 mr-2" />
                  Enabled
                </>
              ) : (
                <>
                  <WifiOff className="h-4 w-4 mr-2" />
                  Disabled
                </>
              )}
            </Button>
          </CardTitle>
          <CardDescription>
            Connect to OBS for automatic session tracking, recording detection, and scene markers
          </CardDescription>
        </CardHeader>
      </Card>
      
      {/* Connection Settings */}
      <Card className={obsConfig.enabled ? '' : 'opacity-50'}>
        <CardHeader>
          <CardTitle>Connection Settings</CardTitle>
          <CardDescription>
            Configure OBS WebSocket connection details
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">
              WebSocket URL
            </label>
            <Input
              type="text"
              value={obsConfig.url}
              onChange={handleUrlChange}
              disabled={!obsConfig.enabled}
              placeholder="ws://localhost:4455"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Default OBS WebSocket port is 4455. Use host.docker.internal for local OBS.
            </p>
          </div>
          
          <div>
            <label className="text-sm font-medium mb-2 block">
              Password
            </label>
            <div className="relative">
              <Input
                type={showPassword ? 'text' : 'password'}
                value={obsConfig.password}
                onChange={handlePasswordChange}
                disabled={!obsConfig.enabled}
                placeholder="Enter OBS WebSocket password"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                disabled={!obsConfig.enabled}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Set in OBS → Tools → WebSocket Server Settings
            </p>
          </div>
          
          {/* Test Connection */}
          <div className="pt-4 border-t">
            <Button
              onClick={handleTest}
              disabled={!canTest || !obsConfig.enabled || testMutation.isPending}
              className="w-full"
            >
              {testMutation.isPending ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-current mr-2" />
                  Testing Connection...
                </>
              ) : (
                <>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Connection
                </>
              )}
            </Button>
          </div>
          
          {/* Test Result */}
          {testResult && (
            <Card className={testResult.ok ? 'border-green-500/50' : 'border-red-500/50'}>
              <CardContent className="py-4">
                <div className="flex items-start space-x-3">
                  {testResult.ok ? (
                    <Check className="h-5 w-5 text-green-500 mt-0.5" />
                  ) : (
                    <X className="h-5 w-5 text-red-500 mt-0.5" />
                  )}
                  <div className="flex-1">
                    <p className="font-medium">
                      {testResult.ok ? 'Connection Successful' : 'Connection Failed'}
                    </p>
                    <p className="text-sm text-muted-foreground">
                      {testResult.reason}
                    </p>
                    {testResult.version && (
                      <p className="text-sm text-muted-foreground mt-1">
                        OBS Version: {testResult.version}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </CardContent>
      </Card>
      
      {/* Features Info */}
      <Card>
        <CardHeader>
          <CardTitle>What OBS Integration Enables</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="flex items-start space-x-3">
              <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Check className="h-3 w-3 text-primary" />
              </div>
              <div>
                <p className="font-medium">Automatic Recording Detection</p>
                <p className="text-sm text-muted-foreground">
                  Process files immediately when recording stops
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Check className="h-3 w-3 text-primary" />
              </div>
              <div>
                <p className="font-medium">Scene Change Markers</p>
                <p className="text-sm text-muted-foreground">
                  Track scene transitions for easier editing
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Check className="h-3 w-3 text-primary" />
              </div>
              <div>
                <p className="font-medium">Recording Guardrails</p>
                <p className="text-sm text-muted-foreground">
                  Pause heavy processing while you're live or recording
                </p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3">
              <div className="w-5 h-5 rounded-full bg-primary/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                <Check className="h-3 w-3 text-primary" />
              </div>
              <div>
                <p className="font-medium">Session Metadata</p>
                <p className="text-sm text-muted-foreground">
                  Capture profile, collection, and duration automatically
                </p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Skip Notice */}
      {!obsConfig.enabled && (
        <Card className="border-blue-500/50 bg-blue-500/10">
          <CardContent className="py-4">
            <div className="flex items-start space-x-3">
              <AlertCircle className="h-5 w-5 text-blue-500 mt-0.5" />
              <div>
                <p className="font-medium">OBS is Optional</p>
                <p className="text-sm text-muted-foreground">
                  StreamOps will still work without OBS by watching your recording folders for new files.
                  You can always enable OBS integration later in Settings.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}