import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { 
  PlayCircle, 
  PauseCircle, 
  XCircle, 
  Clock, 
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronRight,
  FileVideo,
  Film,
  Image,
  Music,
  File
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { formatDuration, formatRelativeTime } from '@/lib/utils'

export default function ActiveJobsTable({ jobs, loading, onViewAll }) {
  const navigate = useNavigate()
  
  // Get icon for job type
  const getJobIcon = (type) => {
    const iconMap = {
      'ffmpeg_remux': FileVideo,
      'ffmpeg_transcode': Film,
      'generate_thumbnails': Image,
      'generate_waveform': Music,
      'scene_detect': Film,
      'create_proxy': FileVideo,
      'index_asset': File
    }
    const Icon = iconMap[type] || File
    return <Icon className="h-4 w-4" />
  }
  
  // Get status icon
  const getStatusIcon = (status) => {
    switch (status) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />
      case 'cancelled':
        return <XCircle className="h-4 w-4 text-gray-500" />
      default:
        return <AlertCircle className="h-4 w-4 text-muted-foreground" />
    }
  }
  
  // Get status badge variant
  const getStatusVariant = (status) => {
    const variantMap = {
      'running': 'primary',
      'pending': 'warning',
      'completed': 'success',
      'failed': 'destructive',
      'cancelled': 'secondary'
    }
    return variantMap[status] || 'secondary'
  }
  
  // Format job name for display
  const formatJobName = (type) => {
    return type
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ')
  }
  
  // Calculate progress percentage
  const getProgress = (job) => {
    if (job.status !== 'running') return null
    if (!job.progress) return 0
    
    // Progress could be a number (0-100) or an object with current/total
    if (typeof job.progress === 'number') {
      return Math.round(job.progress)
    } else if (job.progress.current && job.progress.total) {
      return Math.round((job.progress.current / job.progress.total) * 100)
    }
    return 0
  }
  
  if (loading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Active Jobs</CardTitle>
          <CardDescription>Currently processing tasks</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-16 bg-muted animate-pulse rounded-lg" />
            ))}
          </div>
        </CardContent>
      </Card>
    )
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Active Jobs</CardTitle>
            <CardDescription>
              {jobs && jobs.length > 0 
                ? `${jobs.filter(j => j.status === 'running').length} running, ${jobs.filter(j => j.status === 'pending').length} pending`
                : 'No active jobs'}
            </CardDescription>
          </div>
          {jobs && jobs.length > 0 && (
            <Button 
              variant="outline" 
              size="sm" 
              onClick={onViewAll}
            >
              View All
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {jobs && jobs.length > 0 ? (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[40px]"></TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Asset</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jobs.map((job) => {
                  const progress = getProgress(job)
                  return (
                    <TableRow 
                      key={job.id}
                      className="cursor-pointer hover:bg-accent/50"
                      onClick={() => navigate(`/jobs?id=${job.id}`)}
                    >
                      <TableCell>
                        {getJobIcon(job.type)}
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="font-medium text-sm">
                              {formatJobName(job.type)}
                            </span>
                            {job.priority > 5 && (
                              <Badge variant="outline" className="text-xs">
                                High Priority
                              </Badge>
                            )}
                          </div>
                          {progress !== null && (
                            <div className="flex items-center space-x-2">
                              <div className="w-24 bg-secondary rounded-full h-1.5">
                                <div 
                                  className="bg-primary h-1.5 rounded-full transition-all"
                                  style={{ width: `${progress}%` }}
                                />
                              </div>
                              <span className="text-xs text-muted-foreground">
                                {progress}%
                              </span>
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="max-w-[200px]">
                          <p className="text-sm truncate" title={job.asset_name}>
                            {job.asset_name || 'Unknown'}
                          </p>
                          {job.asset_path && typeof job.asset_path === 'string' && (
                            <p className="text-xs text-muted-foreground truncate" title={job.asset_path}>
                              {job.asset_path.split('/').pop() || job.asset_path}
                            </p>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {getStatusIcon(job.status)}
                          <StatusBadge variant={getStatusVariant(job.status)}>
                            {job.status}
                          </StatusBadge>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="text-sm">
                          {job.started_at && (
                            <p>{formatDuration(job.started_at, job.completed_at)}</p>
                          )}
                          <p className="text-xs text-muted-foreground">
                            {formatRelativeTime(job.created_at)}
                          </p>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          </div>
        ) : (
          <div className="text-center py-12">
            <CheckCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-lg font-medium mb-2">No Active Jobs</h3>
            <p className="text-muted-foreground text-sm">
              All jobs are complete. New recordings will trigger automatic processing.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}