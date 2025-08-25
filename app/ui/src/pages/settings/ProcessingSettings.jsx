import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, RotateCcw, Info, Cpu, Zap, Copy, CheckCircle, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';

const ProcessingSettings = () => {
  const { api } = useApi();
  const queryClient = useQueryClient();
  const [isDirty, setIsDirty] = useState(false);
  const [copied, setCopied] = useState(false);
  const [formData, setFormData] = useState({
    processing: {
      cpu_throttle: 0,
      gpu_throttle: 0,
      default_proxy_resolution: '1080p',
      hardware_acceleration: 'none',
      ffmpeg_path: '/usr/bin/ffmpeg'
    }
  });

  // Fetch settings
  const { data: settings, isLoading: settingsLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then(r => r.data)
  });

  // Fetch system info for GPU capabilities
  const { data: systemInfo } = useQuery({
    queryKey: ['system-info'],
    queryFn: () => api.get('/system/info').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  });

  // Update form when settings load
  useEffect(() => {
    if (settings?.processing) {
      setFormData({ processing: settings.processing });
      setIsDirty(false);
    }
  }, [settings]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: () => {
      queryClient.invalidateQueries(['settings']);
      toast.success('Processing settings saved successfully');
      setIsDirty(false);
    },
    onError: (error) => {
      toast.error(`Failed to save: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({
      processing: {
        ...prev.processing,
        [field]: value
      }
    }));
    setIsDirty(true);
  };

  const handleSave = () => {
    // Validate GPU settings
    if (formData.processing.hardware_acceleration !== 'none' && !systemInfo?.gpu?.present) {
      toast.error('Cannot enable GPU acceleration: No compatible GPU detected');
      return;
    }
    
    saveMutation.mutate(formData);
  };

  const handleReset = () => {
    if (window.confirm('Reset processing settings to defaults?')) {
      api.post('/settings/reset/processing')
        .then(() => {
          queryClient.invalidateQueries(['settings']);
          toast.success('Processing settings reset to defaults');
          setIsDirty(false);
        })
        .catch(err => {
          toast.error(`Failed to reset: ${err.response?.data?.detail || err.message}`);
        });
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Build hardware acceleration options
  const hwAccelOptions = ['none'];
  if (systemInfo?.gpu?.ffmpeg_hwaccels) {
    hwAccelOptions.push(...systemInfo.gpu.ffmpeg_hwaccels);
  }

  if (settingsLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-muted rounded w-1/4"></div>
          <div className="h-64 bg-muted rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-5xl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Processing Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            FFmpeg configuration and hardware acceleration
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            onClick={handleReset}
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

      {/* Processing Configuration */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Processing Configuration</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="space-y-6">
          {/* CPU Throttle */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              <Cpu className="w-4 h-4 inline mr-2" />
              CPU Throttle (%)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0"
                max="100"
                value={formData.processing.cpu_throttle}
                onChange={(e) => handleChange('cpu_throttle', parseInt(e.target.value))}
                className="flex-1"
              />
              <input
                type="number"
                min="0"
                max="100"
                value={formData.processing.cpu_throttle}
                onChange={(e) => handleChange('cpu_throttle', parseInt(e.target.value))}
                className="w-20 px-3 py-2 border border-input rounded-lg bg-background text-foreground"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Limit CPU usage during processing (0 = no limit)
            </p>
          </div>

          {/* GPU Throttle */}
          {systemInfo?.gpu?.present && (
            <div>
              <label className="block text-sm font-medium text-foreground mb-2">
                <Zap className="w-4 h-4 inline mr-2" />
                GPU Throttle (%)
              </label>
              <div className="flex items-center gap-4">
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={formData.processing.gpu_throttle}
                  onChange={(e) => handleChange('gpu_throttle', parseInt(e.target.value))}
                  className="flex-1"
                />
                <input
                  type="number"
                  min="0"
                  max="100"
                  value={formData.processing.gpu_throttle}
                  onChange={(e) => handleChange('gpu_throttle', parseInt(e.target.value))}
                  className="w-20 px-3 py-2 border border-input rounded-lg bg-background text-foreground"
                />
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                Limit GPU usage during processing (0 = no limit)
              </p>
            </div>
          )}

          {/* Default Proxy Resolution */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Default Proxy Resolution
            </label>
            <select
              value={formData.processing.default_proxy_resolution}
              onChange={(e) => handleChange('default_proxy_resolution', e.target.value)}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground"
            >
              <option value="720p">720p (HD)</option>
              <option value="1080p">1080p (Full HD)</option>
              <option value="1440p">1440p (2K)</option>
              <option value="2160p">2160p (4K)</option>
            </select>
            <p className="text-xs text-muted-foreground mt-1">
              Resolution for proxy files used in video editing
            </p>
          </div>

          {/* Hardware Acceleration */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              Hardware Acceleration
            </label>
            <select
              value={formData.processing.hardware_acceleration}
              onChange={(e) => handleChange('hardware_acceleration', e.target.value)}
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground"
            >
              {hwAccelOptions.map(opt => (
                <option key={opt} value={opt}>
                  {opt === 'none' ? 'None (CPU only)' : opt.toUpperCase()}
                </option>
              ))}
            </select>
            
            {formData.processing.hardware_acceleration !== 'none' && !systemInfo?.gpu?.present && (
              <div className="mt-2 p-3 bg-destructive/10 border border-destructive/20 rounded">
                <p className="text-sm text-destructive">
                  <AlertCircle className="w-4 h-4 inline mr-2" />
                  No compatible GPU detected. Hardware acceleration will not work.
                </p>
              </div>
            )}
          </div>

          {/* FFmpeg Path */}
          <div>
            <label className="block text-sm font-medium text-foreground mb-2">
              FFmpeg Path
            </label>
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={formData.processing.ffmpeg_path}
                readOnly
                className="flex-1 px-3 py-2 border border-input rounded-lg bg-muted text-muted-foreground"
              />
              <Button
                variant="outline"
                size="icon"
                onClick={() => copyToClipboard(formData.processing.ffmpeg_path)}
              >
                {copied ? <CheckCircle className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
              </Button>
            </div>
            <div className="mt-2 p-3 bg-primary/10 border border-primary/20 rounded">
                <p className="text-sm text-primary">
                <Info className="w-4 h-4 inline mr-2" />
                FFmpeg is bundled with StreamOps. Path is fixed by the container image.
              </p>
            </div>
          </div>
        </div>
        </CardContent>
      </Card>

      {/* NLE Proxy Compatibility */}
      <Card>
        <CardHeader>
          <CardTitle>NLE Proxy Compatibility</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-2 px-3 text-muted-foreground">Resolution</th>
                <th className="text-center py-2 px-3 text-muted-foreground">Premiere Pro</th>
                <th className="text-center py-2 px-3 text-muted-foreground">DaVinci Resolve</th>
                <th className="text-center py-2 px-3 text-muted-foreground">Final Cut Pro</th>
              </tr>
            </thead>
            <tbody>
              <tr className="border-b border-border">
                <td className="py-2 px-3 font-medium text-foreground">720p</td>
                <td className="text-center py-2 px-3">✅ DNxHR LB</td>
                <td className="text-center py-2 px-3">✅ DNxHR LB</td>
                <td className="text-center py-2 px-3">✅ ProRes Proxy</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 px-3 font-medium text-foreground">1080p</td>
                <td className="text-center py-2 px-3">✅ DNxHR SQ</td>
                <td className="text-center py-2 px-3">✅ DNxHR SQ</td>
                <td className="text-center py-2 px-3">✅ ProRes 422</td>
              </tr>
              <tr className="border-b border-border">
                <td className="py-2 px-3 font-medium text-foreground">1440p</td>
                <td className="text-center py-2 px-3">✅ DNxHR HQ</td>
                <td className="text-center py-2 px-3">✅ DNxHR HQ</td>
                <td className="text-center py-2 px-3">✅ ProRes 422 HQ</td>
              </tr>
              <tr>
                <td className="py-2 px-3 font-medium text-foreground">2160p</td>
                <td className="text-center py-2 px-3">✅ DNxHR HQX</td>
                <td className="text-center py-2 px-3">✅ DNxHR 444</td>
                <td className="text-center py-2 px-3">✅ ProRes 4444</td>
              </tr>
            </tbody>
          </table>
        </div>
        
        <p className="text-xs text-muted-foreground mt-4">
          StreamOps automatically selects the appropriate codec profile based on your NLE and resolution settings.
        </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default ProcessingSettings;