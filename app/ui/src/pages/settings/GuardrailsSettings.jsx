import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Save, RotateCcw, Info, Shield, Cpu, Zap, HardDrive, AlertCircle } from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { cn } from '@/lib/utils';

const GuardrailsSettings = () => {
  const { api } = useApi();
  const queryClient = useQueryClient();
  const [isDirty, setIsDirty] = useState(false);
  const [formData, setFormData] = useState({
    guardrails: {
      pause_when_recording: true,
      cpu_threshold_pct: 80,
      gpu_threshold_pct: 80,
      min_free_disk_gb: 10
    }
  });

  // Fetch settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then(r => r.data)
  });

  // Fetch system info for GPU presence
  const { data: systemInfo } = useQuery({
    queryKey: ['system-info'],
    queryFn: () => api.get('/system/info').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  });

  // Update form when settings load
  useEffect(() => {
    if (settings?.guardrails) {
      setFormData({ guardrails: settings.guardrails });
      setIsDirty(false);
    }
  }, [settings]);

  // Save mutation with hot-apply
  const saveMutation = useMutation({
    mutationFn: async (data) => {
      // First save to persistent storage
      await api.put('/settings', data);
      // Then hot-apply to workers
      await api.post('/guardrails/apply', data.guardrails);
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['settings']);
      toast.success('Guardrails saved and applied immediately');
      setIsDirty(false);
    },
    onError: (error) => {
      toast.error(`Failed to save: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({
      guardrails: {
        ...prev.guardrails,
        [field]: value
      }
    }));
    setIsDirty(true);
  };

  const handleSave = () => {
    saveMutation.mutate(formData);
  };

  const handleReset = () => {
    if (window.confirm('Reset guardrails to defaults?')) {
      api.post('/settings/reset/guardrails')
        .then(() => {
          queryClient.invalidateQueries(['settings']);
          toast.success('Guardrails reset to defaults');
          setIsDirty(false);
        })
        .catch(err => {
          toast.error(`Failed to reset: ${err.response?.data?.detail || err.message}`);
        });
    }
  };

  if (isLoading) {
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
          <h1 className="text-2xl font-bold">Guardrails</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Processing limits and safety thresholds
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
            Save & Apply
          </Button>
        </div>
      </div>

      {/* Help Box */}
      <div className="mb-6 p-4 bg-primary/10 border border-primary/20 rounded-lg">
        <p className="text-sm text-primary">
          <Info className="w-4 h-4 inline mr-2" />
          When any guardrail condition is met, processing jobs pause automatically and resume when conditions return to normal.
        </p>
      </div>

      {/* Guardrails Configuration */}
      <Card>
        <CardHeader>
          <CardTitle>Guardrail Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
        
        {/* Pause When Recording */}
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={formData.guardrails.pause_when_recording}
                onChange={(e) => handleChange('pause_when_recording', e.target.checked)}
                className="sr-only"
              />
              <div className={cn(
                "relative inline-flex h-6 w-11 items-center rounded-full transition",
                formData.guardrails.pause_when_recording 
                  ? 'bg-primary' 
                  : 'bg-muted'
              )}>
                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                  formData.guardrails.pause_when_recording ? 'translate-x-6' : 'translate-x-1'
                }`} />
              </div>
              <span className="ml-3 text-sm font-medium">
                Pause when recording
              </span>
            </label>
            <p className="text-xs text-muted-foreground mt-1 ml-14">
              Automatically pause all processing jobs when OBS is actively recording
            </p>
          </div>
          <Shield className="w-5 h-5 text-muted-foreground ml-4" />
        </div>

        {/* CPU Threshold */}
        <div>
          <label className="block text-sm font-medium mb-2">
            <Cpu className="w-4 h-4 inline mr-2" />
            CPU Threshold (%)
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="50"
              max="100"
              step="5"
              value={formData.guardrails.cpu_threshold_pct}
              onChange={(e) => handleChange('cpu_threshold_pct', parseInt(e.target.value))}
              className="flex-1"
            />
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="50"
                max="100"
                step="5"
                value={formData.guardrails.cpu_threshold_pct}
                onChange={(e) => handleChange('cpu_threshold_pct', parseInt(e.target.value))}
                className="w-20 px-3 py-2 border border-input rounded-lg bg-background text-foreground"
              />
              <span className="text-sm text-muted-foreground">%</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Pause processing when system CPU usage exceeds this threshold
          </p>
          
          {formData.guardrails.cpu_threshold_pct < 70 && (
            <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded">
              <p className="text-xs text-yellow-600 dark:text-yellow-400">
                <AlertCircle className="w-3 h-3 inline mr-1" />
                Low threshold may cause frequent pausing
              </p>
            </div>
          )}
        </div>

        {/* GPU Threshold */}
        {systemInfo?.gpu?.present && (
          <div>
            <label className="block text-sm font-medium mb-2">
              <Zap className="w-4 h-4 inline mr-2" />
              GPU Threshold (%)
            </label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="50"
                max="100"
                step="5"
                value={formData.guardrails.gpu_threshold_pct}
                onChange={(e) => handleChange('gpu_threshold_pct', parseInt(e.target.value))}
                className="flex-1"
              />
              <div className="flex items-center gap-2">
                <input
                  type="number"
                  min="50"
                  max="100"
                  step="5"
                  value={formData.guardrails.gpu_threshold_pct}
                  onChange={(e) => handleChange('gpu_threshold_pct', parseInt(e.target.value))}
                  className="w-20 px-3 py-2 border border-input rounded-lg bg-background text-foreground"
                />
                <span className="text-sm text-muted-foreground">%</span>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Pause processing when GPU usage exceeds this threshold
            </p>
          </div>
        )}

        {/* Minimum Free Disk Space */}
        <div>
          <label className="block text-sm font-medium mb-2">
            <HardDrive className="w-4 h-4 inline mr-2" />
            Minimum Free Disk Space (GB)
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              min="1"
              max="100"
              value={formData.guardrails.min_free_disk_gb}
              onChange={(e) => handleChange('min_free_disk_gb', parseInt(e.target.value))}
              className="flex-1"
            />
            <div className="flex items-center gap-2">
              <input
                type="number"
                min="1"
                max="1000"
                value={formData.guardrails.min_free_disk_gb}
                onChange={(e) => handleChange('min_free_disk_gb', parseInt(e.target.value))}
                className="w-20 px-3 py-2 border border-input rounded-lg bg-background text-foreground"
              />
              <span className="text-sm text-muted-foreground">GB</span>
            </div>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            Pause processing when available disk space falls below this threshold
          </p>
          
          {formData.guardrails.min_free_disk_gb < 5 && (
            <div className="mt-2 p-2 bg-yellow-500/10 border border-yellow-500/20 rounded">
              <p className="text-xs text-yellow-600 dark:text-yellow-400">
                <AlertCircle className="w-3 h-3 inline mr-1" />
                Less than 5GB may cause processing failures
              </p>
            </div>
          )}
        </div>
        </CardContent>
      </Card>

      {/* Current Status */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Current Guardrail Status</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <StatusCard
            label="Recording Status"
            value={formData.guardrails.pause_when_recording ? "Protected" : "Not Protected"}
            status={formData.guardrails.pause_when_recording ? "active" : "inactive"}
            icon={Shield}
          />
          <StatusCard
            label="CPU Protection"
            value={`${formData.guardrails.cpu_threshold_pct}% threshold`}
            status="active"
            icon={Cpu}
          />
          {systemInfo?.gpu?.present && (
            <StatusCard
              label="GPU Protection"
              value={`${formData.guardrails.gpu_threshold_pct}% threshold`}
              status="active"
              icon={Zap}
            />
          )}
          <StatusCard
            label="Disk Protection"
            value={`${formData.guardrails.min_free_disk_gb} GB minimum`}
            status="active"
            icon={HardDrive}
          />
        </div>
        
        <p className="text-xs text-muted-foreground mt-4">
          Changes are applied immediately to all running workers when saved.
        </p>
        </CardContent>
      </Card>
    </div>
  );
};

const StatusCard = ({ label, value, status, icon: Icon }) => (
  <div className="flex items-center justify-between p-3 bg-muted/50 rounded-lg">
    <div className="flex items-center gap-3">
      <Icon className="w-5 h-5 text-muted-foreground" />
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium">{value}</p>
      </div>
    </div>
    <div className={cn(
      "w-2 h-2 rounded-full",
      status === 'active' 
        ? 'bg-green-500' 
        : 'bg-muted'
    )} />
  </div>
);

export default GuardrailsSettings;