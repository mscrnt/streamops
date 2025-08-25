import { useState } from 'react'
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
  Zap
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useHealth, useSystemInfo } from '@/hooks/useApi'
import { useJobs, useActiveJobs, useJobStats } from '@/hooks/useJobs'
import { useAssetStats, useRecentAssets } from '@/hooks/useAssets'
import { useDrives } from '@/hooks/useApi'
import { useSystemStats, useSystemHealth } from '@/hooks/useSystem'
import { formatBytes, formatDuration, formatRelativeTime } from '@/lib/utils'

export default function Dashboard() {
  const [timeRange, setTimeRange] = useState('24h')
  
  // API hooks
  const { data: health } = useHealth()
  const { data: systemInfo } = useSystemInfo()
  const { data: activeJobs } = useActiveJobs()
  const { data: jobStats } = useJobStats(timeRange)
  const { data: assetStats } = useAssetStats(timeRange)
  const { data: recentAssets } = useRecentAssets(5)
  const { data: drives } = useDrives()
  
  // System monitoring via API (no WebSocket needed)
  const { data: systemStats } = useSystemStats()
  const { data: systemHealth } = useSystemHealth()
  
  // Calculate system status
  const systemStatus = systemHealth?.status === 'healthy' ? 'online' : 'offline'
  const activeJobCount = activeJobs?.length || 0
  const queuedJobCount = activeJobs?.filter(job => job.status === 'pending')?.length || 0
  const runningJobCount = activeJobs?.filter(job => job.status === 'running')?.length || 0

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground">
            System overview and activity monitoring
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <div className="flex items-center space-x-2 text-sm">
            <div className={`h-2 w-2 rounded-full ${
              systemStatus === 'online' ? 'bg-green-500 animate-pulse-success' : 'bg-red-500 animate-pulse-error'
            }`} />
            <span className="text-muted-foreground">
              {systemStatus === 'online' ? 'System Online' : 'System Offline'}
            </span>
          </div>
          {systemHealth && (
            <Badge variant={systemHealth.status === 'healthy' ? 'success' : 'warning'}>
              Health: {systemHealth.status}
            </Badge>
          )}
        </div>
      </div>

      {/* System Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Jobs</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{activeJobCount}</div>
            <p className="text-xs text-muted-foreground">
              {runningJobCount} running, {queuedJobCount} queued
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Storage Used</CardTitle>
            <HardDrive className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemStats?.disk ? formatBytes(systemStats.disk.used) : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              {systemStats?.disk ? 
                `${Math.round(systemStats.disk.percent)}% of ${formatBytes(systemStats.disk.total)}` :
                'Loading...'
              }
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemStats?.cpu?.percent ? `${Math.round(systemStats.cpu.percent)}%` : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              {systemStats?.cpu?.load_avg ? 
                `Load: ${systemStats.cpu.load_avg[0].toFixed(2)}` :
                'Measuring...'
              }
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {systemStats?.memory ? `${Math.round(systemStats.memory.percent)}%` : 'N/A'}
            </div>
            <p className="text-xs text-muted-foreground">
              {systemStats?.memory ? 
                `${formatBytes(systemStats.memory.used)} / ${formatBytes(systemStats.memory.total)}` :
                'Memory info unavailable'
              }
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Grid */}
      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {/* Active Jobs */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Active Jobs</CardTitle>
              <Button variant="outline" size="sm">
                View All
              </Button>
            </div>
            <CardDescription>
              Currently running and queued jobs
            </CardDescription>
          </CardHeader>
          <CardContent>
            {activeJobs && activeJobs.length > 0 ? (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Asset</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Progress</TableHead>
                    <TableHead>Started</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeJobs.slice(0, 5).map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>
                        <Badge variant="outline">{job.type}</Badge>
                      </TableCell>
                      <TableCell className="max-w-32 truncate">
                        {job.asset_path || job.asset_id}
                      </TableCell>
                      <TableCell>
                        <StatusBadge status={job.status} />
                      </TableCell>
                      <TableCell>
                        {job.progress ? (
                          <div className="flex items-center space-x-2">
                            <div className="w-20 h-2 bg-muted rounded-full">
                              <div 
                                className="h-2 bg-primary rounded-full" 
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <span className="text-xs">{job.progress}%</span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">N/A</span>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {formatRelativeTime(job.created_at)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <PlayCircle className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium">No Active Jobs</h3>
                <p className="text-muted-foreground">All jobs have completed or no jobs are currently scheduled.</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Job Statistics */}
        <Card>
          <CardHeader>
            <CardTitle>Job Statistics</CardTitle>
            <CardDescription>
              Last 24 hours
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <CheckCircle className="h-4 w-4 text-green-500" />
                <span className="text-sm">Completed</span>
              </div>
              <span className="font-medium">{jobStats?.completed || 0}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <XCircle className="h-4 w-4 text-red-500" />
                <span className="text-sm">Failed</span>
              </div>
              <span className="font-medium">{jobStats?.failed || 0}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Clock className="h-4 w-4 text-yellow-500" />
                <span className="text-sm">Avg Duration</span>
              </div>
              <span className="font-medium">
                {jobStats?.avg_duration ? formatDuration(jobStats.avg_duration) : 'N/A'}
              </span>
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Zap className="h-4 w-4 text-blue-500" />
                <span className="text-sm">Total Jobs</span>
              </div>
              <span className="font-medium">{jobStats?.total || 0}</span>
            </div>
          </CardContent>
        </Card>

        {/* Recent Assets */}
        <Card className="md:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Recent Assets</CardTitle>
              <Button variant="outline" size="sm">
                View All
              </Button>
            </div>
            <CardDescription>
              Recently added media files
            </CardDescription>
          </CardHeader>
          <CardContent>
            {recentAssets && recentAssets.length > 0 ? (
              <div className="space-y-3">
                {recentAssets.map((asset) => (
                  <div key={asset.id} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FileVideo className="h-8 w-8 text-muted-foreground" />
                      <div>
                        <p className="font-medium truncate max-w-64">{asset.filename}</p>
                        <p className="text-xs text-muted-foreground">
                          {formatBytes(asset.file_size)} • {formatRelativeTime(asset.created_at)}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      {asset.has_proxy && <Badge variant="secondary" className="text-xs">Proxy</Badge>}
                      {asset.has_thumbnails && <Badge variant="secondary" className="text-xs">Thumbs</Badge>}
                      <StatusBadge status={asset.status} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileVideo className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium">No Recent Assets</h3>
                <p className="text-muted-foreground">Assets will appear here as they are indexed.</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Drive Status */}
        <Card>
          <CardHeader>
            <CardTitle>Drive Status</CardTitle>
            <CardDescription>
              Monitored storage locations
            </CardDescription>
          </CardHeader>
          <CardContent>
            {drives && drives.length > 0 ? (
              <div className="space-y-3">
                {drives.map((drive) => (
                  <div key={drive.id} className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-sm">{drive.name || drive.path}</p>
                      <p className="text-xs text-muted-foreground">
                        {drive.path}
                      </p>
                    </div>
                    <StatusBadge status={drive.status} />
                  </div>
                ))}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <HardDrive className="h-12 w-12 text-muted-foreground mb-4" />
                <h3 className="text-lg font-medium">No Drives Configured</h3>
                <p className="text-muted-foreground text-xs">
                  Configure drives to start monitoring
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}