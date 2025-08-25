import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Save, RotateCcw, Info, Cpu, HardDrive, 
  Monitor, Package, RefreshCw, Copy, CheckCircle 
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { formatBytes, formatDuration, cn } from '@/lib/utils';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';

const SystemSettings = () => {
  const { api } = useApi();
  const queryClient = useQueryClient();
  const [isDirty, setIsDirty] = useState(false);
  const [copied, setCopied] = useState(false);
  const [formData, setFormData] = useState({
    system: {
      log_level: 'info',
      max_workers: 4,
      worker_timeout: 300,
      temp_dir: '/tmp'
    }
  });

  // Fetch settings
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then(r => r.data)
  });

  // Fetch system info
  const { data: systemInfo, isLoading: infoLoading, error: infoError, refetch: refetchInfo } = useQuery({
    queryKey: ['system-info'],
    queryFn: async () => {
      console.log('Fetching system info...');
      try {
        const response = await api.get('/system/info');
        console.log('System info response:', response.data);
        return response.data;
      } catch (error) {
        console.error('Failed to fetch system info:', error);
        throw error;
      }
    },
    staleTime: 10 * 60 * 1000, // Cache for 10 minutes
  });

  // Update form when settings load
  useEffect(() => {
    if (settings?.system) {
      setFormData({ system: settings.system });
      setIsDirty(false);
    }
  }, [settings]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (data) => api.put('/api/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries(['settings']);
      toast.success('System settings saved successfully');
      setIsDirty(false);
    },
    onError: (error) => {
      toast.error(`Failed to save: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Reset mutation
  const resetMutation = useMutation({
    mutationFn: () => api.post('/api/settings/reset/system'),
    onSuccess: () => {
      queryClient.invalidateQueries(['settings']);
      toast.success('System settings reset to defaults');
      setIsDirty(false);
    },
    onError: (error) => {
      toast.error(`Failed to reset: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({
      system: {
        ...prev.system,
        [field]: value
      }
    }));
    setIsDirty(true);
  };

  const handleSave = () => {
    saveMutation.mutate(formData);
  };

  const handleReset = () => {
    if (window.confirm('Reset system settings to defaults?')) {
      resetMutation.mutate();
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatUptime = (seconds) => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    
    if (days > 0) {
      return `${days}d ${hours}h ${minutes}m`;
    } else if (hours > 0) {
      return `${hours}h ${minutes}m`;
    } else {
      return `${minutes}m`;
    }
  };

  if (settingsLoading || infoLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 dark:bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (infoError) {
    return (
      <div className="p-6">
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
          <p className="text-red-800 dark:text-red-200">
            Failed to load system information: {infoError.message}
          </p>
        </div>
      </div>
    );
  }

  // Debug log
  console.log('SystemInfo data:', systemInfo);
  console.log('Settings data:', settings);

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">System Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Runtime configuration and system information
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            onClick={handleReset}
            variant="outline"
          >
            <RotateCcw className="w-4 h-4 mr-2" />
            Reset
          </Button>
          
          <Button
            onClick={handleSave}
            disabled={!isDirty || saveMutation.isPending}
            loading={saveMutation.isPending}
          >
            <Save className="w-4 h-4 mr-2" />
            Save Changes
          </Button>
        </div>
      </div>

      {/* Configuration Form */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>System Configuration</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Log Level
            </label>
            <select
              value={formData.system.log_level}
              onChange={(e) => handleChange('log_level', e.target.value)}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            >
              <option value="trace">Trace</option>
              <option value="debug">Debug</option>
              <option value="info">Info</option>
              <option value="warn">Warn</option>
              <option value="error">Error</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Max Workers
            </label>
            <input
              type="number"
              min="1"
              max="32"
              value={formData.system.max_workers}
              onChange={(e) => handleChange('max_workers', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Number of concurrent processing workers (1-32)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Worker Timeout (seconds)
            </label>
            <input
              type="number"
              min="60"
              max="3600"
              value={formData.system.worker_timeout}
              onChange={(e) => handleChange('worker_timeout', parseInt(e.target.value))}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Temporary Directory
            </label>
            <input
              type="text"
              value={formData.system.temp_dir}
              readOnly
              className="w-full px-3 py-2 border border-input rounded-lg bg-muted text-muted-foreground cursor-not-allowed"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Path is configured by the container
            </p>
          </div>
        </div>

        {formData.system.max_workers !== settings?.system?.max_workers && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/20 rounded-lg">
            <p className="text-sm text-yellow-600 dark:text-yellow-400">
              <Info className="w-4 h-4 inline mr-2" />
              Worker configuration changes will restart the processing workers
            </p>
          </div>
        )}
        </CardContent>
      </Card>

      {/* System Information */}
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">
            System Information
          </h2>
          <Button
            onClick={() => refetchInfo()}
            variant="ghost"
            size="sm"
          >
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
        </div>

        {/* Version & Platform */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <InfoCard
            icon={Package}
            label="Version"
            value={systemInfo?.version || '1.0.0'}
          />
          <InfoCard
            icon={Monitor}
            label="Platform"
            value={`${systemInfo?.platform?.os || 'Unknown'} (${systemInfo?.platform?.distro || 'unknown'})`}
            subValue={`Kernel ${systemInfo?.platform?.kernel || 'unknown'}`}
          />
          <InfoCard
            icon={Info}
            label="Python"
            value={systemInfo?.python?.version || 'Unknown'}
          />
          <InfoCard
            icon={Monitor}
            label="Uptime"
            value={systemInfo?.uptime_sec ? formatUptime(systemInfo.uptime_sec) : 'Unknown'}
          />
          <InfoCard
            icon={Cpu}
            label="CPU"
            value={`${systemInfo?.cpu?.cores_physical || 0} cores`}
            subValue={`${systemInfo?.cpu?.cores_logical || 0} logical`}
          />
          <InfoCard
            icon={HardDrive}
            label="Memory"
            value={formatBytes(systemInfo?.memory?.total_bytes || 0)}
            subValue={`${formatBytes(systemInfo?.memory?.available_bytes || 0)} available`}
          />
        </div>

        {/* FFmpeg Information */}
        <Card>
          <CardHeader>
            <CardTitle>FFmpeg Information</CardTitle>
          </CardHeader>
          <CardContent>
          
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Version</span>
              <span className="text-sm font-medium">
                {systemInfo?.ffmpeg?.version || 'Not detected'}
              </span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">Path</span>
              <div className="flex items-center gap-2">
                <code className="text-sm font-mono bg-muted px-2 py-1 rounded">
                  {systemInfo?.ffmpeg?.path || '/usr/bin/ffmpeg'}
                </code>
                <Button
                  onClick={() => copyToClipboard(systemInfo?.ffmpeg?.path || '/usr/bin/ffmpeg')}
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                >
                  {copied ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                </Button>
              </div>
            </div>
            
            {systemInfo?.ffmpeg?.build && (
              <details className="mt-3">
                <summary className="cursor-pointer text-sm text-muted-foreground hover:text-foreground">
                  Build flags
                </summary>
                <pre className="mt-2 text-xs bg-muted p-3 rounded overflow-x-auto">
                  {systemInfo.ffmpeg.build}
                </pre>
              </details>
            )}
            
            <div className="mt-3 p-3 bg-blue-500/10 border border-blue-500/20 rounded">
              <p className="text-sm text-blue-600 dark:text-blue-400">
                <Info className="w-4 h-4 inline mr-2" />
                FFmpeg is bundled with StreamOps. Path is fixed by the container image.
              </p>
            </div>
          </div>
          </CardContent>
        </Card>

        {/* GPU Information */}
        <Card>
          <CardHeader>
            <CardTitle>GPU Information</CardTitle>
          </CardHeader>
          <CardContent>
          
          {systemInfo?.gpu?.present ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <span className="text-sm text-muted-foreground">Vendor</span>
                  <p className="text-sm font-medium capitalize">
                    {systemInfo.gpu.vendor || 'Unknown'}
                  </p>
                </div>
                <div>
                  <span className="text-sm text-muted-foreground">Driver</span>
                  <p className="text-sm font-medium">
                    {systemInfo.gpu.driver || 'N/A'}
                  </p>
                </div>
                {systemInfo.gpu.vendor === 'nvidia' && systemInfo.gpu.cuda?.enabled && (
                  <div>
                    <span className="text-sm text-muted-foreground">CUDA</span>
                    <p className="text-sm font-medium">
                      v{systemInfo.gpu.cuda.version}
                    </p>
                  </div>
                )}
                {systemInfo.gpu.vendor === 'amd' && systemInfo.gpu.rocm?.enabled && (
                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400">ROCm</span>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      v{systemInfo.gpu.rocm.version}
                    </p>
                  </div>
                )}
                {systemInfo.gpu.vendor === 'intel' && systemInfo.gpu.level_zero?.enabled && (
                  <div>
                    <span className="text-sm text-gray-600 dark:text-gray-400">Level Zero</span>
                    <p className="text-sm font-medium text-gray-900 dark:text-white">
                      Enabled
                    </p>
                  </div>
                )}
              </div>
              
              {systemInfo.gpu.gpus?.map((gpu, idx) => (
                <div key={idx} className="p-3 bg-muted rounded">
                  <div className="font-medium">{gpu.name}</div>
                  <div className="text-sm text-muted-foreground">
                    VRAM: {formatBytes(gpu.memory_total_bytes)}
                  </div>
                </div>
              ))}
              
              {systemInfo.gpu.ffmpeg_encoders?.length > 0 && (
                <div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">Hardware Encoders</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {systemInfo.gpu.ffmpeg_encoders.map(enc => (
                      <span key={enc} className="px-2 py-1 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 text-xs rounded">
                        {enc}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              {systemInfo.gpu.ffmpeg_hwaccels?.length > 0 && (
                <div>
                  <span className="text-sm text-gray-600 dark:text-gray-400">Hardware Acceleration</span>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {systemInfo.gpu.ffmpeg_hwaccels.map(accel => (
                      <span key={accel} className="px-2 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 text-xs rounded">
                        {accel}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              
              <div className="mt-3 p-3 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded">
                <p className="text-sm text-green-800 dark:text-green-200">
                  {systemInfo.gpu.vendor === 'nvidia' && systemInfo.gpu.cuda?.enabled && (
                    <>CUDA enabled (v{systemInfo.gpu.cuda.version}); </>
                  )}
                  {systemInfo.gpu.vendor === 'amd' && systemInfo.gpu.rocm?.enabled && (
                    <>ROCm enabled (v{systemInfo.gpu.rocm.version}); </>
                  )}
                  {systemInfo.gpu.vendor === 'intel' && systemInfo.gpu.level_zero?.enabled && (
                    <>Intel GPU acceleration enabled; </>
                  )}
                  Hardware encoders available: {systemInfo.gpu.ffmpeg_encoders?.join(', ') || 'None'}.
                </p>
              </div>
            </div>
          ) : (
            <div className="p-4 bg-muted rounded">
              <p className="text-muted-foreground">
                No compatible GPU detected. If your system has an NVIDIA GPU, start the container with 
                <code className="mx-1 px-2 py-1 bg-background border border-border rounded text-sm">--gpus all</code> 
                and install the NVIDIA Container Toolkit.
              </p>
            </div>
          )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

const InfoCard = ({ icon: Icon, label, value, subValue }) => (
  <Card>
    <CardContent className="p-4">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-lg font-semibold mt-1">{value}</p>
          {subValue && (
            <p className="text-xs text-muted-foreground mt-1">{subValue}</p>
          )}
        </div>
        <Icon className="w-5 h-5 text-muted-foreground" />
      </div>
    </CardContent>
  </Card>
);

export default SystemSettings;