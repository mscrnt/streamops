import React, { useState, useEffect } from 'react'
import { 
  Settings as SettingsIcon, 
  Save, 
  RotateCcw, 
  Server, 
  Database, 
  Zap, 
  HardDrive,
  Monitor,
  Bell,
  Shield,
  Download,
  Upload,
  ExternalLink,
  Info
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input, { Textarea, FormField } from '@/components/ui/Input'
import { SimpleSelect } from '@/components/ui/Select'
import * as Tabs from '@radix-ui/react-tabs'
import { useConfig, useUpdateConfig, useSystemInfo } from '@/hooks/useApi'
import { formatBytes } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function Settings() {
  // Local state
  const [hasChanges, setHasChanges] = useState(false)
  const [activeTab, setActiveTab] = useState('system')
  
  // API hooks
  const { data: config, isLoading: configLoading } = useConfig()
  const { data: systemInfo } = useSystemInfo()
  const updateConfig = useUpdateConfig()

  // Local config state
  const [localConfig, setLocalConfig] = useState(config || {})

  // Update local config when API data changes
  useEffect(() => {
    if (config) {
      setLocalConfig(config)
      setHasChanges(false)
    }
  }, [config])

  const handleConfigChange = (section, key, value) => {
    setLocalConfig(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }))
    setHasChanges(true)
  }

  const handleSaveConfig = async () => {
    try {
      await updateConfig.mutateAsync(localConfig)
      setHasChanges(false)
    } catch (error) {
      toast.error('Failed to save configuration')
    }
  }

  const handleResetConfig = () => {
    if (config) {
      setLocalConfig(config)
      setHasChanges(false)
      toast.success('Configuration reset')
    }
  }

  const logLevelOptions = [
    { value: 'DEBUG', label: 'Debug' },
    { value: 'INFO', label: 'Info' },
    { value: 'WARNING', label: 'Warning' },
    { value: 'ERROR', label: 'Error' },
  ]

  const themeOptions = [
    { value: 'light', label: 'Light' },
    { value: 'dark', label: 'Dark' },
    { value: 'auto', label: 'Auto' },
  ]

  const tabs = [
    { value: 'system', label: 'System', icon: Server },
    { value: 'processing', label: 'Processing', icon: Zap },
    { value: 'storage', label: 'Storage', icon: HardDrive },
    { value: 'interface', label: 'Interface', icon: Monitor },
    { value: 'notifications', label: 'Notifications', icon: Bell },
    { value: 'security', label: 'Security', icon: Shield },
  ]

  if (configLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-muted rounded w-1/4" />
          <div className="h-64 bg-muted rounded" />
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Settings</h1>
          <p className="text-muted-foreground">
            Configure StreamOps system settings
          </p>
        </div>
        <div className="flex items-center space-x-2">
          {hasChanges && (
            <Button variant="outline" onClick={handleResetConfig}>
              <RotateCcw className="h-4 w-4 mr-2" />
              Reset
            </Button>
          )}
          <Button 
            onClick={handleSaveConfig}
            loading={updateConfig.isLoading}
            disabled={!hasChanges}
          >
            <Save className="h-4 w-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </div>

      {hasChanges && (
        <Card className="border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/20">
          <CardContent className="p-4">
            <div className="flex items-center space-x-2 text-yellow-800 dark:text-yellow-200">
              <Info className="h-4 w-4" />
              <span className="text-sm font-medium">You have unsaved changes</span>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Settings Tabs */}
      <Tabs.Root value={activeTab} onValueChange={setActiveTab} className="w-full">
        <Tabs.List className="grid grid-cols-6 gap-1 bg-muted p-1 rounded-lg">
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <Tabs.Trigger
                key={tab.value}
                value={tab.value}
                className="flex items-center justify-center space-x-2 py-2 px-3 text-sm font-medium rounded-md transition-colors data-[state=active]:bg-background data-[state=active]:text-foreground data-[state=inactive]:text-muted-foreground hover:text-foreground"
              >
                <Icon className="h-4 w-4" />
                <span className="hidden sm:inline">{tab.label}</span>
              </Tabs.Trigger>
            )
          })}
        </Tabs.List>

        {/* System Settings */}
        <Tabs.Content value="system" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>System Configuration</CardTitle>
              <CardDescription>
                Core system settings and runtime configuration
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField label="Log Level">
                <SimpleSelect
                  options={logLevelOptions}
                  value={localConfig.system?.log_level || 'INFO'}
                  onValueChange={(value) => handleConfigChange('system', 'log_level', value)}
                />
              </FormField>

              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="Max Workers">
                  <Input
                    type="number"
                    min="1"
                    max="16"
                    value={localConfig.system?.max_workers || 4}
                    onChange={(e) => handleConfigChange('system', 'max_workers', parseInt(e.target.value))}
                  />
                </FormField>

                <FormField label="Worker Timeout (seconds)">
                  <Input
                    type="number"
                    min="30"
                    max="3600"
                    value={localConfig.system?.worker_timeout || 300}
                    onChange={(e) => handleConfigChange('system', 'worker_timeout', parseInt(e.target.value))}
                  />
                </FormField>
              </div>

              <FormField label="Temporary Directory">
                <Input
                  placeholder="/tmp/streamops"
                  value={localConfig.system?.temp_dir || ''}
                  onChange={(e) => handleConfigChange('system', 'temp_dir', e.target.value)}
                />
              </FormField>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Information</CardTitle>
              <CardDescription>
                Current system status and resources
              </CardDescription>
            </CardHeader>
            <CardContent>
              {systemInfo ? (
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Version</p>
                    <p className="text-sm text-muted-foreground">{systemInfo.version}</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Platform</p>
                    <p className="text-sm text-muted-foreground">{systemInfo.platform}</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Python Version</p>
                    <p className="text-sm text-muted-foreground">{systemInfo.python_version}</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">CPU Cores</p>
                    <p className="text-sm text-muted-foreground">{systemInfo.cpu_count}</p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Memory</p>
                    <p className="text-sm text-muted-foreground">
                      {formatBytes(systemInfo.memory_total)}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Uptime</p>
                    <p className="text-sm text-muted-foreground">{systemInfo.uptime}</p>
                  </div>
                </div>
              ) : (
                <p className="text-muted-foreground">System information not available</p>
              )}
            </CardContent>
          </Card>
        </Tabs.Content>

        {/* Processing Settings */}
        <Tabs.Content value="processing" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Processing Configuration</CardTitle>
              <CardDescription>
                FFmpeg and media processing settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="CPU Throttle (%)">
                  <Input
                    type="number"
                    min="10"
                    max="100"
                    value={localConfig.processing?.cpu_limit || 70}
                    onChange={(e) => handleConfigChange('processing', 'cpu_limit', parseInt(e.target.value))}
                  />
                </FormField>

                <FormField label="GPU Throttle (%)">
                  <Input
                    type="number"
                    min="10"
                    max="100"
                    value={localConfig.processing?.gpu_limit || 80}
                    onChange={(e) => handleConfigChange('processing', 'gpu_limit', parseInt(e.target.value))}
                  />
                </FormField>
              </div>

              <FormField label="FFmpeg Path">
                <Input
                  placeholder="/usr/bin/ffmpeg"
                  value={localConfig.processing?.ffmpeg_path || ''}
                  onChange={(e) => handleConfigChange('processing', 'ffmpeg_path', e.target.value)}
                />
              </FormField>

              <FormField label="Default Proxy Resolution">
                <SimpleSelect
                  options={[
                    { value: '720p', label: '720p (1280x720)' },
                    { value: '1080p', label: '1080p (1920x1080)' },
                    { value: '1440p', label: '1440p (2560x1440)' },
                  ]}
                  value={localConfig.processing?.default_proxy_resolution || '1080p'}
                  onValueChange={(value) => handleConfigChange('processing', 'default_proxy_resolution', value)}
                />
              </FormField>

              <FormField label="Hardware Acceleration">
                <SimpleSelect
                  options={[
                    { value: 'none', label: 'None' },
                    { value: 'nvenc', label: 'NVIDIA NVENC' },
                    { value: 'qsv', label: 'Intel Quick Sync' },
                    { value: 'vaapi', label: 'VA-API' },
                  ]}
                  value={localConfig.processing?.hardware_acceleration || 'none'}
                  onValueChange={(value) => handleConfigChange('processing', 'hardware_acceleration', value)}
                />
              </FormField>
            </CardContent>
          </Card>
        </Tabs.Content>

        {/* Storage Settings */}
        <Tabs.Content value="storage" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Storage Configuration</CardTitle>
              <CardDescription>
                File storage and cleanup settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField label="Cleanup Policy">
                <SimpleSelect
                  options={[
                    { value: 'never', label: 'Never delete files' },
                    { value: 'on_request', label: 'Delete on request only' },
                    { value: 'auto_30d', label: 'Auto-delete after 30 days' },
                    { value: 'auto_90d', label: 'Auto-delete after 90 days' },
                  ]}
                  value={localConfig.storage?.cleanup_policy || 'on_request'}
                  onValueChange={(value) => handleConfigChange('storage', 'cleanup_policy', value)}
                />
              </FormField>

              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="Max Cache Size (GB)">
                  <Input
                    type="number"
                    min="1"
                    max="1000"
                    value={localConfig.storage?.max_cache_size || 50}
                    onChange={(e) => handleConfigChange('storage', 'max_cache_size', parseInt(e.target.value))}
                  />
                </FormField>

                <FormField label="Thumbnail Quality">
                  <SimpleSelect
                    options={[
                      { value: 'low', label: 'Low (Fast)' },
                      { value: 'medium', label: 'Medium' },
                      { value: 'high', label: 'High (Slow)' },
                    ]}
                    value={localConfig.storage?.thumbnail_quality || 'medium'}
                    onValueChange={(value) => handleConfigChange('storage', 'thumbnail_quality', value)}
                  />
                </FormField>
              </div>

              <FormField label="Enable Deduplication">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localConfig.storage?.enable_deduplication || false}
                    onChange={(e) => handleConfigChange('storage', 'enable_deduplication', e.target.checked)}
                    className="rounded border-border"
                  />
                  <span className="text-sm">Detect and remove duplicate files</span>
                </label>
              </FormField>
            </CardContent>
          </Card>
        </Tabs.Content>

        {/* Interface Settings */}
        <Tabs.Content value="interface" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Interface Configuration</CardTitle>
              <CardDescription>
                User interface and display settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField label="Default Theme">
                <SimpleSelect
                  options={themeOptions}
                  value={localConfig.interface?.theme || 'auto'}
                  onValueChange={(value) => handleConfigChange('interface', 'theme', value)}
                />
              </FormField>

              <div className="grid gap-4 md:grid-cols-2">
                <FormField label="Items Per Page">
                  <SimpleSelect
                    options={[
                      { value: '25', label: '25 items' },
                      { value: '50', label: '50 items' },
                      { value: '100', label: '100 items' },
                    ]}
                    value={localConfig.interface?.items_per_page || '50'}
                    onValueChange={(value) => handleConfigChange('interface', 'items_per_page', value)}
                  />
                </FormField>

                <FormField label="Refresh Interval (seconds)">
                  <Input
                    type="number"
                    min="5"
                    max="300"
                    value={localConfig.interface?.refresh_interval || 30}
                    onChange={(e) => handleConfigChange('interface', 'refresh_interval', parseInt(e.target.value))}
                  />
                </FormField>
              </div>

              <FormField label="Show Advanced Options">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localConfig.interface?.show_advanced || false}
                    onChange={(e) => handleConfigChange('interface', 'show_advanced', e.target.checked)}
                    className="rounded border-border"
                  />
                  <span className="text-sm">Show advanced configuration options</span>
                </label>
              </FormField>
            </CardContent>
          </Card>
        </Tabs.Content>

        {/* Notifications Settings */}
        <Tabs.Content value="notifications" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Notification Configuration</CardTitle>
              <CardDescription>
                Configure alerts and notifications
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <h4 className="font-medium">Email Notifications</h4>
                <FormField label="SMTP Server">
                  <Input
                    placeholder="smtp.example.com"
                    value={localConfig.notifications?.smtp_server || ''}
                    onChange={(e) => handleConfigChange('notifications', 'smtp_server', e.target.value)}
                  />
                </FormField>

                <div className="grid gap-4 md:grid-cols-2">
                  <FormField label="SMTP Port">
                    <Input
                      type="number"
                      placeholder="587"
                      value={localConfig.notifications?.smtp_port || ''}
                      onChange={(e) => handleConfigChange('notifications', 'smtp_port', parseInt(e.target.value))}
                    />
                  </FormField>

                  <FormField label="From Email">
                    <Input
                      type="email"
                      placeholder="streamops@example.com"
                      value={localConfig.notifications?.from_email || ''}
                      onChange={(e) => handleConfigChange('notifications', 'from_email', e.target.value)}
                    />
                  </FormField>
                </div>
              </div>

              <div className="space-y-3">
                <h4 className="font-medium">Webhook Notifications</h4>
                <FormField label="Webhook URL">
                  <Input
                    placeholder="https://hooks.slack.com/services/..."
                    value={localConfig.notifications?.webhook_url || ''}
                    onChange={(e) => handleConfigChange('notifications', 'webhook_url', e.target.value)}
                  />
                </FormField>
              </div>

              <div className="space-y-3">
                <h4 className="font-medium">Notification Types</h4>
                <div className="grid gap-3 md:grid-cols-2">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={localConfig.notifications?.job_completed || false}
                      onChange={(e) => handleConfigChange('notifications', 'job_completed', e.target.checked)}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Job completed</span>
                  </label>

                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={localConfig.notifications?.job_failed || false}
                      onChange={(e) => handleConfigChange('notifications', 'job_failed', e.target.checked)}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Job failed</span>
                  </label>

                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={localConfig.notifications?.system_errors || false}
                      onChange={(e) => handleConfigChange('notifications', 'system_errors', e.target.checked)}
                      className="rounded border-border"
                    />
                    <span className="text-sm">System errors</span>
                  </label>

                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={localConfig.notifications?.drive_offline || false}
                      onChange={(e) => handleConfigChange('notifications', 'drive_offline', e.target.checked)}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Drive offline</span>
                  </label>
                </div>
              </div>
            </CardContent>
          </Card>
        </Tabs.Content>

        {/* Security Settings */}
        <Tabs.Content value="security" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Security Configuration</CardTitle>
              <CardDescription>
                Authentication and security settings
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <FormField label="Enable Authentication">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localConfig.security?.enable_auth || false}
                    onChange={(e) => handleConfigChange('security', 'enable_auth', e.target.checked)}
                    className="rounded border-border"
                  />
                  <span className="text-sm">Require authentication to access the interface</span>
                </label>
              </FormField>

              {localConfig.security?.enable_auth && (
                <>
                  <FormField label="Session Timeout (minutes)">
                    <Input
                      type="number"
                      min="15"
                      max="1440"
                      value={localConfig.security?.session_timeout || 480}
                      onChange={(e) => handleConfigChange('security', 'session_timeout', parseInt(e.target.value))}
                    />
                  </FormField>

                  <FormField label="Admin Password">
                    <Input
                      type="password"
                      placeholder="Leave blank to keep current"
                      value={localConfig.security?.admin_password || ''}
                      onChange={(e) => handleConfigChange('security', 'admin_password', e.target.value)}
                    />
                  </FormField>
                </>
              )}

              <FormField label="Enable HTTPS">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localConfig.security?.enable_https || false}
                    onChange={(e) => handleConfigChange('security', 'enable_https', e.target.checked)}
                    className="rounded border-border"
                  />
                  <span className="text-sm">Force HTTPS connections</span>
                </label>
              </FormField>

              <FormField label="Allow File Downloads">
                <label className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={localConfig.security?.allow_downloads || true}
                    onChange={(e) => handleConfigChange('security', 'allow_downloads', e.target.checked)}
                    className="rounded border-border"
                  />
                  <span className="text-sm">Allow users to download media files</span>
                </label>
              </FormField>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Backup & Export</CardTitle>
              <CardDescription>
                Configuration backup and data export options
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex space-x-2">
                <Button variant="outline">
                  <Download className="h-4 w-4 mr-2" />
                  Export Config
                </Button>
                <Button variant="outline">
                  <Upload className="h-4 w-4 mr-2" />
                  Import Config
                </Button>
                <Button variant="outline">
                  <Database className="h-4 w-4 mr-2" />
                  Export Database
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Back up your configuration and database for safekeeping or migration to another system.
              </p>
            </CardContent>
          </Card>
        </Tabs.Content>
      </Tabs.Root>
    </div>
  )
}