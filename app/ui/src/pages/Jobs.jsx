import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { useSearchParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Play, Pause, RefreshCw, Trash2, X, ChevronDown, Filter,
  CheckSquare, Square, MoreVertical, Eye, Download, Copy,
  AlertCircle, Clock, CheckCircle, XCircle, Loader2,
  Archive, Terminal, FileJson, Activity, Zap, Info,
  ChevronRight, Calendar, ArrowUpDown, Search
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { formatDuration, formatRelativeTime, formatBytes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import JobDetailsDrawer from '@/components/jobs/JobDetailsDrawer'
import BulkActionBar from '@/components/jobs/BulkActionBar'
import toast from 'react-hot-toast'

export default function Jobs() {
  const navigate = useNavigate()
  const { api } = useApi()
  const queryClient = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const wsRef = useRef(null)
  
  // Extract URL params
  const status = searchParams.get('status') || 'all'
  const type = searchParams.get('type') || 'all'
  const dateField = searchParams.get('date_field') || 'created_at'
  const startDate = searchParams.get('start')
  const endDate = searchParams.get('end')
  const sort = searchParams.get('sort') || 'created_at'
  const order = searchParams.get('order') || 'desc'
  const page = parseInt(searchParams.get('page') || '1')
  const perPage = parseInt(searchParams.get('per_page') || '50')
  
  // Local state
  const [selected, setSelected] = useState(new Set())
  const [detailsJobId, setDetailsJobId] = useState(null)
  const [queuePaused, setQueuePaused] = useState(false)
  const [confirmClearQueue, setConfirmClearQueue] = useState(false)
  const [activeMenuId, setActiveMenuId] = useState(null)
  
  // Build query params
  const queryParams = useMemo(() => {
    const params = new URLSearchParams()
    if (status !== 'all') params.set('status', status)
    if (type !== 'all') params.set('type', type)
    params.set('date_field', dateField)
    if (startDate) params.set('start', startDate)
    if (endDate) params.set('end', endDate)
    params.set('sort', sort)
    params.set('order', order)
    params.set('page', page.toString())
    params.set('per_page', perPage.toString())
    return params.toString()
  }, [status, type, dateField, startDate, endDate, sort, order, page, perPage])
  
  // Fetch jobs list
  const { data: jobsData, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs', queryParams],
    queryFn: async () => {
      const response = await api.get(`/jobs/?${queryParams}`)
      return response.data
    },
    refetchInterval: 5000, // Poll every 5 seconds
    staleTime: 2000
  })
  
  // Fetch summary stats
  const { data: summary } = useQuery({
    queryKey: ['jobs', 'summary'],
    queryFn: async () => {
      const response = await api.get('/jobs/summary?window=24h')
      return response.data
    },
    refetchInterval: 5000,
    staleTime: 2000
  })
  
  // Check queue status
  useEffect(() => {
    async function checkQueueStatus() {
      try {
        const response = await api.get('/config')
        setQueuePaused(response.data?.['queue.paused'] === 'true')
      } catch (error) {
        console.error('Failed to check queue status:', error)
      }
    }
    checkQueueStatus()
  }, [api])
  
  // WebSocket connection for real-time updates
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/jobs/ws`
    
    function connectWebSocket() {
      wsRef.current = new WebSocket(wsUrl)
      
      wsRef.current.onopen = () => {
        console.log('Jobs WebSocket connected')
      }
      
      wsRef.current.onmessage = (event) => {
        // Skip non-JSON messages (like 'pong' responses or other plain text)
        if (typeof event.data === 'string' && !event.data.startsWith('{') && !event.data.startsWith('[')) {
          // Silently ignore plain text messages
          return
        }
        
        try {
          const data = JSON.parse(event.data)
          
          // Handle different event types
          switch (data.type) {
            case 'job_progress':
            case 'job_state':
              // Invalidate jobs list to refresh
              queryClient.invalidateQueries(['jobs'])
              queryClient.invalidateQueries(['jobs', 'summary'])
              break
            case 'queue_state':
              setQueuePaused(data.paused)
              break
            case 'queue_cleared':
              queryClient.invalidateQueries(['jobs'])
              queryClient.invalidateQueries(['jobs', 'summary'])
              toast.success(`Cleared ${data.deleted_count} queued jobs`)
              break
          }
        } catch (error) {
          console.error('WebSocket message error:', error, 'Data:', event.data)
        }
      }
      
      wsRef.current.onerror = (error) => {
        console.error('WebSocket error:', error)
      }
      
      wsRef.current.onclose = () => {
        console.log('WebSocket disconnected, retrying in 5s...')
        setTimeout(connectWebSocket, 5000)
      }
      
      // Send ping every 30s to keep alive
      const pingInterval = setInterval(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send('ping')
        }
      }, 30000)
      
      return () => clearInterval(pingInterval)
    }
    
    const cleanup = connectWebSocket()
    
    return () => {
      cleanup?.()
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [queryClient])
  
  // Update URL params
  const updateParams = useCallback((updates) => {
    const newParams = new URLSearchParams(searchParams)
    Object.entries(updates).forEach(([key, value]) => {
      if (value) {
        newParams.set(key, value)
      } else {
        newParams.delete(key)
      }
    })
    setSearchParams(newParams)
  }, [searchParams, setSearchParams])
  
  // Selection handlers
  const toggleSelection = useCallback((jobId) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(jobId)) {
        next.delete(jobId)
      } else {
        next.add(jobId)
      }
      return next
    })
  }, [])
  
  const toggleAllOnPage = useCallback((checked) => {
    if (jobsData?.items) {
      setSelected(prev => {
        const next = new Set(prev)
        jobsData.items.forEach(job => {
          if (checked) {
            next.add(job.id)
          } else {
            next.delete(job.id)
          }
        })
        return next
      })
    }
  }, [jobsData])
  
  const clearSelection = useCallback(() => {
    setSelected(new Set())
  }, [])
  
  // Action mutations
  const cancelMutation = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/cancel`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      queryClient.invalidateQueries(['jobs', 'summary'])
      toast.success('Job canceled')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to cancel job')
    }
  })
  
  const retryMutation = useMutation({
    mutationFn: async (jobId) => {
      const response = await api.post(`/jobs/${jobId}/retry`)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['jobs'])
      queryClient.invalidateQueries(['jobs', 'summary'])
      toast.success('Job queued for retry')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to retry job')
    }
  })
  
  const bulkActionMutation = useMutation({
    mutationFn: async ({ action, ids }) => {
      const response = await api.post('/jobs/bulk', { action, ids })
      return response.data
    },
    onSuccess: (data, variables) => {
      queryClient.invalidateQueries(['jobs'])
      queryClient.invalidateQueries(['jobs', 'summary'])
      const successCount = data.results.filter(r => r.ok).length
      toast.success(`${variables.action} ${successCount} jobs`)
      clearSelection()
    },
    onError: (error) => {
      toast.error(error.message || 'Bulk action failed')
    }
  })
  
  const queueActionMutation = useMutation({
    mutationFn: async (action) => {
      const response = await api.post(`/queue/${action}`)
      return response.data
    },
    onSuccess: (data, action) => {
      if (action === 'pause') {
        setQueuePaused(true)
        toast.success('Queue paused')
      } else if (action === 'resume') {
        setQueuePaused(false)
        toast.success('Queue resumed')
      } else if (action === 'clear') {
        queryClient.invalidateQueries(['jobs'])
        queryClient.invalidateQueries(['jobs', 'summary'])
        setConfirmClearQueue(false)
      }
    },
    onError: (error) => {
      toast.error(error.message || 'Queue action failed')
    }
  })
  
  // Get status badge
  const getStatusBadge = (job) => {
    // Handle both direct status string and job object
    const status = typeof job === 'string' ? job : (job.state || job.status)
    
    const variants = {
      queued: { variant: 'warning', icon: Clock },
      pending: { variant: 'warning', icon: Clock },
      running: { variant: 'info', icon: Activity },
      completed: { variant: 'success', icon: CheckCircle },
      deferred: { variant: 'outline', icon: Pause },
      failed: { variant: 'destructive', icon: XCircle },
      canceled: { variant: 'secondary', icon: X }
    }
    
    const config = variants[status] || { variant: 'secondary', icon: Info }
    const Icon = config.icon
    
    // For deferred jobs, show blocking reason tooltip
    const title = typeof job === 'object' && status === 'deferred' && job.blocked_reason ? 
      `Deferred: ${job.blocked_reason.replace(/_/g, ' ').replace(':', ': ')}` : 
      undefined
    
    // For deferred jobs with countdown, create a badge with countdown
    if (status === 'deferred' && typeof job === 'object' && job.next_run_at) {
      return <DeferredBadge job={job} config={config} Icon={Icon} title={title} />
    }
    
    return (
      <Badge 
        variant={config.variant} 
        className="capitalize font-semibold text-xs px-2.5 py-1"
        title={title}
      >
        <Icon className={cn("w-4 h-4 mr-1.5", config.animate && "animate-spin")} />
        {status}
      </Badge>
    )
  }
  
  // Deferred badge with countdown
  const DeferredBadge = ({ job, config, Icon, title }) => {
    const [timeLeft, setTimeLeft] = useState('')
    
    useEffect(() => {
      const updateCountdown = () => {
        const formatted = formatNextRun(job.next_run_at)
        setTimeLeft(formatted || '')
      }
      
      // Update immediately
      updateCountdown()
      
      // Update every second
      const interval = setInterval(updateCountdown, 1000)
      
      return () => clearInterval(interval)
    }, [job.next_run_at])
    
    return (
      <Badge 
        variant={config.variant} 
        className="capitalize font-semibold text-xs px-2.5 py-1"
        title={title}
      >
        <Icon className="w-4 h-4 mr-1.5" />
        <span>deferred</span>
        {timeLeft && (
          <span className="ml-1 font-normal opacity-90">({timeLeft})</span>
        )}
      </Badge>
    )
  }
  
  // Format next run time for deferred jobs
  const formatNextRun = (nextRunAt) => {
    if (!nextRunAt) return null
    const nextRun = new Date(nextRunAt)
    const now = new Date()
    const diffMs = nextRun - now
    
    if (diffMs <= 0) return 'Now'
    if (diffMs < 60000) return `${Math.ceil(diffMs / 1000)}s`
    if (diffMs < 3600000) return `${Math.ceil(diffMs / 60000)}m`
    if (diffMs < 86400000) return `${Math.ceil(diffMs / 3600000)}h`
    return formatRelativeTime(nextRunAt)
  }
  
  // Countdown component for deferred jobs
  const DeferredCountdown = ({ nextRunAt }) => {
    const [timeLeft, setTimeLeft] = useState('')
    
    useEffect(() => {
      const updateCountdown = () => {
        const formatted = formatNextRun(nextRunAt)
        setTimeLeft(formatted || '')
      }
      
      // Update immediately
      updateCountdown()
      
      // Update every second
      const interval = setInterval(updateCountdown, 1000)
      
      return () => clearInterval(interval)
    }, [nextRunAt])
    
    if (!timeLeft) return null
    
    return (
      <span className="text-xs text-muted-foreground">
        in {timeLeft}
      </span>
    )
  }
  
  // Get job type label
  const getJobTypeLabel = (type) => {
    const labels = {
      ffmpeg_remux: 'Remux',
      ffmpeg_transcode: 'Transcode',
      proxy: 'Proxy',
      thumbnail: 'Thumbnails',
      index: 'Index',
      move: 'Move',
      copy: 'Copy',
      archive: 'Archive',
      custom: 'Custom'
    }
    return labels[type] || type
  }
  
  // Format duration for display
  const formatJobDuration = (job) => {
    // If duration_sec is provided, use it
    if (job.duration_sec) {
      return formatDuration(job.duration_sec)
    }
    
    // For running jobs, calculate from started_at to now
    if ((job.state || job.status) === 'running' && job.started_at) {
      const started = new Date(job.started_at)
      const now = new Date()
      const sec = Math.floor((now - started) / 1000)
      return formatDuration(sec)
    }
    
    // For completed/failed jobs, calculate from started_at to ended_at
    if (job.started_at && job.ended_at) {
      const started = new Date(job.started_at)
      const ended = new Date(job.ended_at)
      const sec = Math.floor((ended - started) / 1000)
      if (sec >= 0) {
        return formatDuration(sec)
      }
    }
    
    return '—'
  }
  
  // Close menu on outside click
  useEffect(() => {
    const handleClickOutside = () => {
      setActiveMenuId(null)
    }
    if (activeMenuId) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [activeMenuId])
  
  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading jobs...</p>
        </div>
      </div>
    )
  }
  
  // Error state
  if (error) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
          <h3 className="text-lg font-medium mb-2">Couldn't load jobs</h3>
          <p className="text-muted-foreground mb-4">{error.message}</p>
          <Button onClick={() => refetch()}>
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    )
  }
  
  const jobs = jobsData?.items || []
  const total = jobsData?.total || 0
  const totalPages = Math.ceil(total / perPage)
  const selectedCount = selected.size
  const allOnPageSelected = jobs.length > 0 && jobs.every(job => selected.has(job.id))
  
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Jobs</h1>
        <p className="text-muted-foreground">
          Monitor and manage processing queue
        </p>
      </div>
      
      {/* Queue Paused Banner */}
      {queuePaused && (
        <div className="bg-warning/10 border border-warning/20 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Pause className="w-5 h-5 text-warning" />
            <div>
              <p className="font-medium">Processing queue is paused</p>
              <p className="text-sm text-muted-foreground">
                New jobs will not start until resumed
              </p>
            </div>
          </div>
          <Button
            variant="warning"
            onClick={() => queueActionMutation.mutate('resume')}
            disabled={queueActionMutation.isPending}
          >
            <Play className="w-4 h-4 mr-2" />
            Resume Queue
          </Button>
        </div>
      )}
      
      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Running
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.running || 0}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Queued
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{summary?.queued || 0}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Deferred
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-muted-foreground">
              {summary?.deferred || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Completed (24h)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {summary?.completed_24h || 0}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Failed (24h)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {summary?.failed_24h || 0}
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Queue Controls */}
      <div className="flex items-center gap-2">
        {!queuePaused ? (
          <Button
            variant="outline"
            onClick={() => queueActionMutation.mutate('pause')}
            disabled={queueActionMutation.isPending}
          >
            <Pause className="w-4 h-4 mr-2" />
            Pause Queue
          </Button>
        ) : (
          <Button
            variant="primary"
            onClick={() => queueActionMutation.mutate('resume')}
            disabled={queueActionMutation.isPending}
          >
            <Play className="w-4 h-4 mr-2" />
            Resume Queue
          </Button>
        )}
        
        {confirmClearQueue ? (
          <div className="flex items-center gap-2 px-3 py-2 bg-destructive/10 border border-destructive/20 rounded-lg">
            <p className="text-sm">Remove all queued jobs?</p>
            <Button
              size="sm"
              variant="destructive"
              onClick={() => queueActionMutation.mutate('clear')}
              disabled={queueActionMutation.isPending}
            >
              Yes, Clear
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setConfirmClearQueue(false)}
            >
              Cancel
            </Button>
          </div>
        ) : (
          <Button
            variant="outline"
            onClick={() => setConfirmClearQueue(true)}
            disabled={summary?.queued === 0}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Clear Queued
          </Button>
        )}
        
        <div className="ml-auto">
          <Button
            variant="outline"
            onClick={() => refetch()}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
        </div>
      </div>
      
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 p-4 bg-muted/50 rounded-lg">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Status:</label>
          <select
            value={status}
            onChange={(e) => updateParams({ status: e.target.value, page: '1' })}
            className="px-3 py-1.5 border border-input rounded-lg bg-background text-sm"
          >
            <option value="all">All status</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="deferred">Deferred</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="canceled">Canceled</option>
          </select>
        </div>
        
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Type:</label>
          <select
            value={type}
            onChange={(e) => updateParams({ type: e.target.value, page: '1' })}
            className="px-3 py-1.5 border border-input rounded-lg bg-background text-sm"
          >
            <option value="all">All types</option>
            <option value="ffmpeg_remux">Remux</option>
            <option value="ffmpeg_transcode">Transcode</option>
            <option value="proxy">Proxy</option>
            <option value="thumbnail">Thumbnails</option>
            <option value="index">Index</option>
            <option value="move">Move</option>
            <option value="copy">Copy</option>
            <option value="archive">Archive</option>
            <option value="custom">Custom</option>
          </select>
        </div>
        
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium">Sort by:</label>
          <select
            value={`${sort}:${order}`}
            onChange={(e) => {
              const [newSort, newOrder] = e.target.value.split(':')
              updateParams({ sort: newSort, order: newOrder, page: '1' })
            }}
            className="px-3 py-1.5 border border-input rounded-lg bg-background text-sm"
          >
            <option value="created_at:desc">Created (newest)</option>
            <option value="created_at:asc">Created (oldest)</option>
            <option value="updated_at:desc">Updated (recent)</option>
            <option value="updated_at:asc">Updated (oldest)</option>
            <option value="type:asc">Type (A-Z)</option>
            <option value="type:desc">Type (Z-A)</option>
            <option value="state:asc">Status (A-Z)</option>
            <option value="state:desc">Status (Z-A)</option>
          </select>
        </div>
        
        {(status !== 'all' || type !== 'all') && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => updateParams({ status: null, type: null, page: '1' })}
          >
            <X className="w-4 h-4 mr-1" />
            Clear Filters
          </Button>
        )}
      </div>
      
      {/* Bulk Action Bar */}
      {selectedCount > 0 && (
        <BulkActionBar
          selectedCount={selectedCount}
          onAction={(action) => {
            bulkActionMutation.mutate({
              action,
              ids: Array.from(selected)
            })
          }}
          onClear={clearSelection}
        />
      )}
      
      {/* Jobs Table */}
      <Card>
        <CardContent className="p-0">
          {jobs.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="border-b border-border">
                  <tr className="text-left">
                    <th className="p-3">
                      <button
                        onClick={() => toggleAllOnPage(!allOnPageSelected)}
                        className="p-1"
                      >
                        {allOnPageSelected ? (
                          <CheckSquare className="w-4 h-4" />
                        ) : (
                          <Square className="w-4 h-4" />
                        )}
                      </button>
                    </th>
                    <th className="p-3 text-sm font-medium">Job</th>
                    <th className="p-3 text-sm font-medium">Asset</th>
                    <th className="p-3 text-sm font-medium">Status</th>
                    <th className="p-3 text-sm font-medium">Progress</th>
                    <th className="p-3 text-sm font-medium">Duration</th>
                    <th className="p-3 text-sm font-medium">Created</th>
                    <th className="p-3 text-sm font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr 
                      key={job.id}
                      className="border-b border-border hover:bg-muted/50 transition-colors"
                    >
                      <td className="p-3">
                        <button
                          onClick={() => toggleSelection(job.id)}
                          className="p-1"
                        >
                          {selected.has(job.id) ? (
                            <CheckSquare className="w-4 h-4" />
                          ) : (
                            <Square className="w-4 h-4" />
                          )}
                        </button>
                      </td>
                      <td className="p-3">
                        <div>
                          <div className="font-medium">
                            {getJobTypeLabel(job.type)}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            {job.id.slice(0, 8)}
                          </div>
                        </div>
                      </td>
                      <td className="p-3">
                        {job.asset_name ? (
                          <button
                            onClick={() => navigate(`/recordings?id=${job.asset_id}`)}
                            className="text-primary hover:underline"
                          >
                            {job.asset_name}
                          </button>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          {getStatusBadge(job)}
                        </div>
                      </td>
                      <td className="p-3">
                        {(() => {
                          const status = job.state || job.status
                          
                          // Show progress bar for running jobs
                          if (status === 'running' && job.progress > 0) {
                            return (
                              <div className="w-32">
                                <div className="flex items-center gap-2 mb-1">
                                  <span className="text-sm font-medium">
                                    {Math.round(job.progress)}%
                                  </span>
                                  {job.eta_sec && (
                                    <span className="text-xs text-muted-foreground">
                                      ETA {formatDuration(job.eta_sec)}
                                    </span>
                                  )}
                                </div>
                                <div className="h-2 bg-muted rounded-full overflow-hidden">
                                  <div
                                    className="h-full bg-primary transition-all duration-300"
                                    style={{ width: `${job.progress}%` }}
                                  />
                                </div>
                              </div>
                            )
                          }
                          
                          // Show 100% for completed jobs
                          if (status === 'completed') {
                            return (
                              <span className="text-sm text-success">100%</span>
                            )
                          }
                          
                          // Show appropriate text for other states
                          if (status === 'failed') {
                            return (
                              <span className="text-sm text-destructive">Failed</span>
                            )
                          }
                          
                          if (status === 'canceled') {
                            return (
                              <span className="text-sm text-muted-foreground">Canceled</span>
                            )
                          }
                          
                          if (status === 'queued' || status === 'pending') {
                            return (
                              <span className="text-sm text-muted-foreground">Queued</span>
                            )
                          }
                          
                          // Default
                          return (
                            <span className="text-muted-foreground">—</span>
                          )
                        })()}
                      </td>
                      <td className="p-3">
                        <span className="text-sm">
                          {formatJobDuration(job)}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="text-sm">
                          <div>{formatRelativeTime(job.created_at)}</div>
                          {job.started_at && (
                            <div className="text-xs text-muted-foreground">
                              Started {formatRelativeTime(job.started_at)}
                            </div>
                          )}
                          {job.ended_at && (
                            <div className="text-xs text-muted-foreground">
                              Ended {formatRelativeTime(job.ended_at)}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="p-3">
                        <div className="relative">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation()
                              setActiveMenuId(activeMenuId === job.id ? null : job.id)
                            }}
                          >
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                          {activeMenuId === job.id && (
                            <div className="absolute right-0 top-10 z-20 w-48 bg-popover border border-border rounded-lg shadow-lg py-1">
                              <button
                                className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                                onClick={(e) => {
                                  e.stopPropagation()
                                  setDetailsJobId(job.id)
                                  setActiveMenuId(null)
                                }}
                              >
                                <Eye className="w-4 h-4 inline mr-2" />
                                View Details
                              </button>
                              {job.deferred && (
                                <button
                                  className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                                  onClick={async (e) => {
                                    e.stopPropagation()
                                    try {
                                      await api.post(`/jobs/${job.id}/force-run`)
                                      toast.success('Job forced to run')
                                      queryClient.invalidateQueries(['jobs'])
                                    } catch (error) {
                                      toast.error('Failed to force run job')
                                    }
                                    setActiveMenuId(null)
                                  }}
                                >
                                  <Zap className="w-4 h-4 inline mr-2" />
                                  Force Run Now
                                </button>
                              )}
                              {(job.state || job.status) === 'failed' && (
                                <button
                                  className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    retryMutation.mutate(job.id)
                                    setActiveMenuId(null)
                                  }}
                                >
                                  <RefreshCw className="w-4 h-4 inline mr-2" />
                                  Retry
                                </button>
                              )}
                              {['queued', 'running'].includes(job.state || job.status) && (
                                <button
                                  className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    cancelMutation.mutate(job.id)
                                    setActiveMenuId(null)
                                  }}
                                >
                                  <X className="w-4 h-4 inline mr-2" />
                                  Cancel
                                </button>
                              )}
                              {['completed', 'failed', 'canceled'].includes(job.state || job.status) && (
                                <button
                                  className="w-full px-3 py-2 text-sm text-left hover:bg-accent hover:text-accent-foreground text-destructive"
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    bulkActionMutation.mutate({
                                      action: 'delete',
                                      ids: [job.id]
                                    })
                                    setActiveMenuId(null)
                                  }}
                                >
                                  <Trash2 className="w-4 h-4 inline mr-2" />
                                  Delete Record
                                </button>
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-12 text-center">
              <Archive className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No jobs yet</h3>
              <p className="text-muted-foreground">
                Jobs will appear here when assets are processed
              </p>
            </div>
          )}
        </CardContent>
      </Card>
      
      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Showing {(page - 1) * perPage + 1} to {Math.min(page * perPage, total)} of {total} jobs
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => updateParams({ page: (page - 1).toString() })}
              disabled={page === 1}
            >
              Previous
            </Button>
            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum
                if (totalPages <= 5) {
                  pageNum = i + 1
                } else if (page <= 3) {
                  pageNum = i + 1
                } else if (page >= totalPages - 2) {
                  pageNum = totalPages - 4 + i
                } else {
                  pageNum = page - 2 + i
                }
                
                return (
                  <Button
                    key={pageNum}
                    variant={pageNum === page ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => updateParams({ page: pageNum.toString() })}
                  >
                    {pageNum}
                  </Button>
                )
              })}
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => updateParams({ page: (page + 1).toString() })}
              disabled={page === totalPages}
            >
              Next
            </Button>
          </div>
        </div>
      )}
      
      {/* Job Details Drawer */}
      {detailsJobId && (
        <JobDetailsDrawer
          jobId={detailsJobId}
          onClose={() => setDetailsJobId(null)}
          onRetry={(id) => retryMutation.mutate(id)}
          onCancel={(id) => cancelMutation.mutate(id)}
        />
      )}
    </div>
  )
}