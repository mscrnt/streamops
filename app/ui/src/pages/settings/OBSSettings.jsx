import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Save, RotateCcw, Video, CheckCircle, XCircle, 
  Loader2, Eye, EyeOff, TestTube, Info 
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';

const OBSSettings = () => {
  const { api } = useApi();
  const queryClient = useQueryClient();
  const [isDirty, setIsDirty] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [formData, setFormData] = useState({
    obs: {
      url: 'ws://host.docker.internal:4455',
      password: '',
      auto_connect: true
    }
  });

  // Fetch settings
  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => api.get('/settings').then(r => r.data)
  });

  // Update form when settings load
  useEffect(() => {
    if (settings?.obs) {
      setFormData({ obs: settings.obs });
      setIsDirty(false);
    }
  }, [settings]);

  // Save mutation
  const saveMutation = useMutation({
    mutationFn: (data) => api.put('/settings', data),
    onSuccess: (response) => {
      queryClient.invalidateQueries(['settings']);
      toast.success('OBS settings saved successfully');
      setIsDirty(false);
      
      // If auto-connect is enabled, trigger connection
      if (formData.obs.auto_connect) {
        toast.info('Reconnecting to OBS...');
        // The backend should handle reconnection
      }
    },
    onError: (error) => {
      toast.error(`Failed to save: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Test connection mutation
  const testMutation = useMutation({
    mutationFn: (credentials) => api.post('/system/probe-obs', credentials),
    onSuccess: (response) => {
      setTestResult(response.data);
      if (response.data.ok) {
        toast.success(`Connected to OBS ${response.data.version || ''}`);
      } else {
        toast.error(response.data.reason || 'Connection failed');
      }
    },
    onError: (error) => {
      setTestResult({ ok: false, reason: error.message });
      toast.error(`Test failed: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleChange = (field, value) => {
    setFormData(prev => ({
      obs: {
        ...prev.obs,
        [field]: value
      }
    }));
    setIsDirty(true);
    setTestResult(null); // Clear test result when settings change
  };

  const handleSave = () => {
    // Don't send masked password if it hasn't changed
    const dataToSave = { ...formData };
    if (dataToSave.obs.password === '********') {
      // Keep existing password
      delete dataToSave.obs.password;
    }
    saveMutation.mutate(dataToSave);
  };

  const handleReset = () => {
    if (window.confirm('Reset OBS settings to defaults?')) {
      api.post('/settings/reset/obs')
        .then(() => {
          queryClient.invalidateQueries(['settings']);
          toast.success('OBS settings reset to defaults');
          setIsDirty(false);
          setTestResult(null);
        })
        .catch(err => {
          toast.error(`Failed to reset: ${err.response?.data?.detail || err.message}`);
        });
    }
  };

  const handleTest = () => {
    const testData = {
      url: formData.obs.url,
      password: formData.obs.password === '********' 
        ? settings?.obs?.password || '' 
        : formData.obs.password
    };
    testMutation.mutate(testData);
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
          <h1 className="text-2xl font-bold">OBS Settings</h1>
          <p className="text-sm text-muted-foreground mt-1">
            WebSocket connection and recording detection
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

      {/* Connection Configuration */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle>Connection Configuration</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="space-y-6">
          {/* WebSocket URL */}
          <div>
            <label className="block text-sm font-medium mb-2">
              WebSocket URL
            </label>
            <input
              type="text"
              value={formData.obs.url}
              onChange={(e) => handleChange('url', e.target.value)}
              placeholder="ws://host.docker.internal:4455"
              className="w-full px-3 py-2 border border-input rounded-lg bg-background text-foreground"
            />
            <p className="text-xs text-muted-foreground mt-1">
              Default: ws://host.docker.internal:4455 (use this for OBS on host machine)
            </p>
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-medium mb-2">
              Password
            </label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                value={formData.obs.password}
                onChange={(e) => handleChange('password', e.target.value)}
                placeholder="Enter OBS WebSocket password"
                className="w-full px-3 py-2 pr-10 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Set in OBS → Tools → WebSocket Server Settings
            </p>
          </div>

          {/* Auto-connect */}
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <label className="flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={formData.obs.auto_connect}
                  onChange={(e) => handleChange('auto_connect', e.target.checked)}
                  className="sr-only"
                />
                <div className={cn(
                  "relative inline-flex h-6 w-11 items-center rounded-full transition",
                  formData.obs.auto_connect 
                    ? 'bg-primary' 
                    : 'bg-muted'
                )}>
                  <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition ${
                    formData.obs.auto_connect ? 'translate-x-6' : 'translate-x-1'
                  }`} />
                </div>
                <span className="ml-3 text-sm font-medium">
                  Auto-connect on startup
                </span>
              </label>
              <p className="text-xs text-muted-foreground mt-1 ml-14">
                Automatically establish connection when StreamOps starts
              </p>
            </div>
          </div>

          {/* Test Connection */}
          <div className="pt-4 border-t border-border">
            <Button
              variant="secondary"
              onClick={handleTest}
              disabled={testMutation.isPending}
              loading={testMutation.isPending}
            >
              <TestTube className="w-4 h-4 mr-2" />
              Test Connection
            </Button>
            
            {testResult && (
              <div className={cn(
                "mt-3 p-3 rounded-lg flex items-start gap-3 border",
                testResult.ok 
                  ? 'bg-green-500/10 border-green-500/20' 
                  : 'bg-destructive/10 border-destructive/20'
              )}>
                {testResult.ok ? (
                  <CheckCircle className="w-5 h-5 text-green-500 mt-0.5" />
                ) : (
                  <XCircle className="w-5 h-5 text-destructive mt-0.5" />
                )}
                <div className="flex-1">
                  <p className={cn(
                    "text-sm font-medium",
                    testResult.ok 
                      ? 'text-green-600 dark:text-green-400' 
                      : 'text-destructive'
                  )}>
                    {testResult.ok ? 'Connection successful' : 'Connection failed'}
                  </p>
                  {testResult.version && (
                    <p className="text-xs text-green-600 dark:text-green-400 mt-1">
                      OBS Studio version: {testResult.version}
                    </p>
                  )}
                  {testResult.reason && (
                    <p className="text-xs text-destructive mt-1">
                      {testResult.reason}
                    </p>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
        </CardContent>
      </Card>

      {/* Help Section */}
      <div className="p-4 bg-primary/10 border border-primary/20 rounded-lg">
        <h3 className="text-sm font-semibold text-primary mb-2">
          <Info className="w-4 h-4 inline mr-2" />
          Setting up OBS WebSocket
        </h3>
        <ol className="text-sm text-primary space-y-1 ml-6">
          <li>1. Open OBS Studio (v28.0 or later)</li>
          <li>2. Go to Tools → WebSocket Server Settings</li>
          <li>3. Enable "Enable WebSocket server"</li>
          <li>4. Set a password and note the port (default: 4455)</li>
          <li>5. Click "Show Connect Info" to verify settings</li>
          <li>6. Enter the same password here and test connection</li>
        </ol>
      </div>

      {/* Features */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>OBS Integration Features</CardTitle>
        </CardHeader>
        <CardContent>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FeatureCard
            icon={Video}
            title="Recording Detection"
            description="Automatically detect when OBS is recording"
          />
          <FeatureCard
            icon={Video}
            title="Scene Markers"
            description="Mark scene changes during recording"
          />
          <FeatureCard
            icon={Video}
            title="Auto-pause Processing"
            description="Pause jobs while recording to prevent dropped frames"
          />
          <FeatureCard
            icon={Video}
            title="Session Tracking"
            description="Group recordings into sessions with metadata"
          />
        </div>
        </CardContent>
      </Card>
    </div>
  );
};

const FeatureCard = ({ icon: Icon, title, description }) => (
  <div className="flex items-start gap-3 p-3 bg-muted/50 rounded-lg">
    <Icon className="w-5 h-5 text-primary mt-0.5" />
    <div>
      <p className="text-sm font-medium">{title}</p>
      <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
    </div>
  </div>
);

export default OBSSettings;