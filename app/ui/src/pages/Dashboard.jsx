import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Activity, 
  HardDrive, 
  Clock, 
  CheckCircle, 
  XCircle, 
  PlayCircle,
  PauseCircle,
  TrendingUp,
  FileVideo,
  Zap,
  Cpu,
  MemoryStick,
  AlertTriangle,
  RefreshCw,
  FolderSync,
  Image,
  Layers,
  Video,
  Shield,
  Wifi,
  WifiOff
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useApi } from '@/hooks/useApi'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'
import MetricCard from '@/components/dashboard/MetricCard'
import DriveTile from '@/components/dashboard/DriveTile'
import ActiveJobsTable from '@/components/dashboard/ActiveJobsTable'
import RecentAssetsList from '@/components/dashboard/RecentAssetsList'
import JobStatsCard from '@/components/dashboard/JobStatsCard'
import GuardrailsStrip from '@/components/dashboard/GuardrailsStrip'
import QuickActions from '@/components/dashboard/QuickActions'
import toast from 'react-hot-toast'

export default function Dashboard() {
  const navigate = useNavigate()
  const { api } = useApi()
  const [timeRange, setTimeRange] = useState('24h')
  
  // Fetch system summary
  const { data: summary, isLoading: summaryLoading, refetch: refetchSummary } = useQuery({
    queryKey: ['system', 'summary'],
    queryFn: async () => {
      const response = await api.get('/system/summary')
      return response.data
    },
    refetchInterval: 5000, // Refresh every 5 seconds
    staleTime: 2000
  })
  
  // Fetch system metrics for sparklines
  const { data: metrics } = useQuery({
    queryKey: ['system', 'metrics', { window: '5m', step: '5s' }],
    queryFn: async () => {
      const response = await api.get('/system/metrics', {
        params: { window: '5m', step: '5s' }
      })
      return response.data
    },
    refetchInterval: 10000,
    staleTime: 5000
  })
  
  // Fetch drive status
  const { data: drives, isLoading: drivesLoading } = useQuery({
    queryKey: ['drives', 'status'],
    queryFn: async () => {
      const response = await api.get('/drives/status')
      return response.data
    },
    refetchInterval: 10000,
    staleTime: 5000
  })
  
  // Fetch active jobs
  const { data: activeJobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'active', { limit: 10 }],
    queryFn: async () => {
      const response = await api.get('/jobs/active', {
        params: { limit: 10 }
      })
      return response.data
    },
    refetchInterval: 5000,
    staleTime: 2000
  })
  
  // Fetch recent assets
  const { data: recentAssets, isLoading: assetsLoading } = useQuery({
    queryKey: ['assets', 'recent', { limit: 10 }],
    queryFn: async () => {
      const response = await api.get('/assets/recent', {
        params: { limit: 10 }
      })
      return response.data
    },
    refetchInterval: 15000,
    staleTime: 10000
  })
  
  // System action mutation
  const actionMutation = useMutation({
    mutationFn: async (action) => {
      const response = await api.post('/system/actions', { action })
      return response.data
    },
    onSuccess: (data) => {
      toast.success(data.message || 'Action completed successfully')
      refetchSummary()
    },
    onError: (error) => {
      toast.error(error.message || 'Action failed')
    }
  })
  
  // Loading state
  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading dashboard...</p>
        </div>
      </div>
    )
  }
  
  // Default values if data not loaded
  const health = summary?.health || { status: 'unknown', reason: null }
  const cpu = summary?.cpu || { percent: 0, load_avg: [0, 0, 0] }
  const memory = summary?.memory || { percent: 0, used: 0, total: 1 }
  const gpu = summary?.gpu || { present: false, percent: 0 }
  const storage = summary?.storage || { used_bytes: 0, total_bytes: 1 }
  const jobs = summary?.jobs || {
    running: 0,
    queued: 0,
    active_last10: 0,
    completed_24h: 0,
    failed_24h: 0,
    avg_duration_24h_sec: null
  }
  const obs = summary?.obs || { connected: false, version: null, recording: false }
  const guardrails = summary?.guardrails || { active: false, reason: null }
  
  // Determine health badge variant
  const healthVariant = health.status === 'healthy' ? 'success' : 
                        health.status === 'degraded' ? 'warning' : 'destructive'
  
  return (
    <div className="space-y-6 p-6">
      {/* Header with Health Status */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            System overview and activity monitoring
          </p>
        </div>
        <div className="flex items-center space-x-3">
          {/* System Health Badge */}
          <Badge 
            variant={healthVariant}
            className="cursor-pointer"
            onClick={() => navigate('/settings#diagnostics')}
          >
            <div className={`h-2 w-2 rounded-full mr-2 ${
              health.status === 'healthy' ? 'bg-green-500 animate-pulse' :
              health.status === 'degraded' ? 'bg-yellow-500 animate-pulse' :
              'bg-red-500 animate-pulse'
            }`} />
            System {health.status}
            {health.reason && (
              <span className="ml-1 text-xs">({health.reason})</span>
            )}
          </Badge>
        </div>
      </div>
      
      {/* Guardrails and OBS Status Strip */}
      <GuardrailsStrip 
        guardrails={guardrails}
        obs={obs}
        onManageOBS={() => navigate('/settings#obs')}
      />
      
      {/* System Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <MetricCard
          title="Active Jobs"
          value={jobs.running + jobs.queued}
          subvalue={`${jobs.running} running, ${jobs.queued} queued`}
          icon={Activity}
          trend={metrics?.queue_depth}
          variant={jobs.running > 0 ? 'primary' : 'secondary'}
        />
        
        <MetricCard
          title="Storage Used"
          value={formatBytes(storage.used_bytes)}
          subvalue={`${Math.round((storage.used_bytes / storage.total_bytes) * 100)}% of ${formatBytes(storage.total_bytes)}`}
          icon={HardDrive}
          variant={storage.used_bytes / storage.total_bytes > 0.9 ? 'warning' : 'default'}
        />
        
        <MetricCard
          title="CPU Usage"
          value={`${Math.round(cpu.percent)}%`}
          subvalue={`Load: ${cpu.load_avg[0]?.toFixed(2) || '0.00'}`}
          icon={Cpu}
          trend={metrics?.cpu}
          variant={cpu.percent > 80 ? 'warning' : 'default'}
        />
        
        <MetricCard
          title="Memory Usage"
          value={`${Math.round(memory.percent)}%`}
          subvalue={`${formatBytes(memory.used)} / ${formatBytes(memory.total)}`}
          icon={MemoryStick}
          trend={metrics?.memory}
          variant={memory.percent > 85 ? 'warning' : 'default'}
        />
        
        {gpu.present && (
          <MetricCard
            title="GPU Usage"
            value={`${Math.round(gpu.percent)}%`}
            subvalue="Graphics Processing"
            icon={Zap}
            trend={metrics?.gpu}
            variant={gpu.percent > 60 ? 'warning' : 'default'}
          />
        )}
      </div>
      
      {/* Quick Actions */}
      <QuickActions 
        onAction={(action) => actionMutation.mutate(action)}
        disabled={actionMutation.isPending}
      />
      
      {/* Main Content Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Active Jobs - 2 columns wide */}
        <div className="lg:col-span-2">
          <ActiveJobsTable 
            jobs={activeJobs || []}
            loading={jobsLoading}
            onViewAll={() => navigate('/jobs?sort=updated_at:desc&filter=active')}
          />
        </div>
        
        {/* Job Statistics */}
        <JobStatsCard
          stats={{
            completed: jobs.completed_24h,
            failed: jobs.failed_24h,
            avgDuration: jobs.avg_duration_24h_sec,
            total: jobs.completed_24h + jobs.failed_24h
          }}
          timeRange="24h"
          onOpenReport={() => navigate('/jobs?range=24h')}
        />
      </div>
      
      {/* Second Row */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Recent Assets - 2 columns wide */}
        <div className="lg:col-span-2">
          <RecentAssetsList
            assets={recentAssets || []}
            loading={assetsLoading}
            onViewAll={() => navigate('/assets?sort=created_at:desc')}
          />
        </div>
        
        {/* Drive Status */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Drive Status</CardTitle>
              <Button 
                variant="outline" 
                size="sm"
                onClick={() => navigate('/drives')}
              >
                Manage
              </Button>
            </div>
            <CardDescription>
              Monitored storage locations
            </CardDescription>
          </CardHeader>
          <CardContent>
            {!drivesLoading && drives && drives.length > 0 ? (
              <div className="space-y-3">
                {drives.map((drive) => (
                  <DriveTile
                    key={drive.id}
                    drive={drive}
                    onClick={() => navigate(`/drives?select=${drive.id}`)}
                  />
                ))}
              </div>
            ) : !drivesLoading && (!drives || drives.length === 0) ? (
              <div className="text-center py-8">
                <HardDrive className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
                <h3 className="text-lg font-medium mb-2">No Drives Configured</h3>
                <p className="text-muted-foreground text-sm mb-4">
                  No monitored drives yet. Open Drives to map your recording and editing folders.
                </p>
                <Button onClick={() => navigate('/drives')}>
                  Configure Drives
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-16 bg-muted animate-pulse rounded-lg" />
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}