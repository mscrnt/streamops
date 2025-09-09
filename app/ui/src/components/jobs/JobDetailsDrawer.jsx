import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  X, RefreshCw, Copy, Download, Terminal, FileJson, 
  Info, Eye, Clock, CheckCircle, XCircle, Loader2,
  ChevronRight, ExternalLink, AlertCircle, Maximize2
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { formatDuration, formatRelativeTime, formatBytes } from '@/lib/utils'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function JobDetailsDrawer({ 
  jobId, 
  onClose, 
  onRetry, 
  onCancel 
}) {
  const { api } = useApi()
  const [activeTab, setActiveTab] = useState('overview')
  const [logsExpanded, setLogsExpanded] = useState(false)
  
  // Fetch job details
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['jobs', jobId],
    queryFn: async () => {
      const response = await api.get(`/jobs/${jobId}`)
      return response.data
    },
    refetchInterval: 2000, // Refresh every 2 seconds for live updates
    staleTime: 1000
  })
  
  const job = data?.job
  const logs = data?.logs_tail
  
  // Copy to clipboard
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text)
    toast.success(`${label} copied to clipboard`)
  }
  
  // Get status badge
  const getStatusBadge = (status) => {
    const variants = {
      queued: { variant: 'warning', icon: Clock },
      pending: { variant: 'warning', icon: Clock },
      running: { variant: 'info', icon: Loader2, animate: true },
      completed: { variant: 'success', icon: CheckCircle },
      failed: { variant: 'destructive', icon: XCircle },
      canceled: { variant: 'secondary', icon: X }
    }
    
    const config = variants[status] || { variant: 'secondary', icon: Info }
    const Icon = config.icon
    
    return (
      <Badge variant={config.variant} className="capitalize">
        <Icon className={cn("w-3 h-3 mr-1", config.animate && "animate-spin")} />
        {status}
      </Badge>
    )
  }
  
  // Calculate duration
  const getDuration = () => {
    if (!job) return '—'
    
    if (job.ended_at && job.started_at) {
      const start = new Date(job.started_at)
      const end = new Date(job.ended_at)
      const sec = (end - start) / 1000
      return formatDuration(sec)
    }
    
    if (job.status === 'running' && job.started_at) {
      const start = new Date(job.started_at)
      const now = new Date()
      const sec = (now - start) / 1000
      return formatDuration(sec)
    }
    
    return '—'
  }
  
  // Close on escape
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    window.addEventListener('keydown', handleEscape)
    return () => window.removeEventListener('keydown', handleEscape)
  }, [onClose])
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Drawer */}
      <div className="fixed right-0 top-0 bottom-0 w-[600px] bg-background border-l border-border z-50 flex flex-col animate-in slide-in-from-right">
        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-start justify-between mb-4">
            <div>
              <h2 className="text-xl font-semibold mb-2">Job Details</h2>
              {job && (
                <div className="flex items-center gap-3">
                  {getStatusBadge(job.status)}
                  <span className="text-sm text-muted-foreground">
                    ID: {job.id.slice(0, 8)}
                  </span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => copyToClipboard(job.id, 'Job ID')}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              )}
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
          
          {/* Action buttons */}
          {job && (
            <div className="flex items-center gap-2">
              {job.status === 'failed' && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onRetry(job.id)}
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Retry
                </Button>
              )}
              {['queued', 'running'].includes(job.status) && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onCancel(job.id)}
                >
                  <X className="w-4 h-4 mr-2" />
                  Cancel
                </Button>
              )}
            </div>
          )}
        </div>
        
        {/* Tabs */}
        <div className="border-b border-border">
          <div className="flex">
            <button
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                activeTab === 'overview' 
                  ? "border-primary text-primary" 
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
              onClick={() => setActiveTab('overview')}
            >
              <Info className="w-4 h-4 inline mr-2" />
              Overview
            </button>
            <button
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                activeTab === 'logs' 
                  ? "border-primary text-primary" 
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
              onClick={() => setActiveTab('logs')}
            >
              <Terminal className="w-4 h-4 inline mr-2" />
              Logs
            </button>
            <button
              className={cn(
                "px-4 py-2 text-sm font-medium border-b-2 transition-colors",
                activeTab === 'json' 
                  ? "border-primary text-primary" 
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
              onClick={() => setActiveTab('json')}
            >
              <FileJson className="w-4 h-4 inline mr-2" />
              JSON
            </button>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-8 h-8 animate-spin text-primary" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-destructive mx-auto mb-4" />
              <p className="text-muted-foreground">{error.message}</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() => refetch()}
                className="mt-4"
              >
                Retry
              </Button>
            </div>
          ) : job && (
            <>
              {/* Overview Tab */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Basic Info */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Job Information</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-muted-foreground">Type</span>
                          <p className="font-medium">{job.type}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Status</span>
                          <div className="mt-1">
                            {getStatusBadge(job.status)}
                          </div>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Duration</span>
                          <p className="font-medium">{getDuration()}</p>
                        </div>
                        <div>
                          <span className="text-muted-foreground">Progress</span>
                          <p className="font-medium">
                            {job.progress ? `${Math.round(job.progress)}%` : '—'}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Asset Info */}
                  {job.asset_name && (
                    <Card>
                      <CardHeader>
                        <CardTitle className="text-sm">Asset</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="font-medium">{job.asset_name}</p>
                            {job.asset_id && (
                              <p className="text-xs text-muted-foreground mt-1">
                                ID: {job.asset_id.slice(0, 8)}
                              </p>
                            )}
                          </div>
                          {job.asset_id && (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() => window.location.href = `/recordings?id=${job.asset_id}`}
                            >
                              <ExternalLink className="w-4 h-4 mr-2" />
                              Open Asset
                            </Button>
                          )}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                  
                  {/* Timestamps */}
                  <Card>
                    <CardHeader>
                      <CardTitle className="text-sm">Timestamps</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Created</span>
                        <span>{job.created_at ? formatRelativeTime(job.created_at) : '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Started</span>
                        <span>{job.started_at ? formatRelativeTime(job.started_at) : '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Ended</span>
                        <span>{job.ended_at ? formatRelativeTime(job.ended_at) : '—'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-muted-foreground">Updated</span>
                        <span>{job.updated_at ? formatRelativeTime(job.updated_at) : '—'}</span>
                      </div>
                    </CardContent>
                  </Card>
                  
                  {/* Error Info */}
                  {job.error && (
                    <Card className="border-destructive/50">
                      <CardHeader>
                        <CardTitle className="text-sm text-destructive">Error</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <pre className="text-xs p-3 bg-destructive/10 rounded-lg overflow-x-auto">
                          {job.error}
                        </pre>
                      </CardContent>
                    </Card>
                  )}
                </div>
              )}
              
              {/* Logs Tab */}
              {activeTab === 'logs' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Last 100 lines of job output
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setLogsExpanded(true)}
                    >
                      <Maximize2 className="w-4 h-4 mr-2" />
                      Expand
                    </Button>
                  </div>
                  
                  {logs ? (
                    <pre className="text-xs p-4 bg-muted/50 rounded-lg overflow-x-auto font-mono">
                      {logs}
                    </pre>
                  ) : (
                    <div className="text-center py-8">
                      <Terminal className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
                      <p className="text-muted-foreground">No logs available</p>
                    </div>
                  )}
                  
                  {/* Expanded logs modal */}
                  {logsExpanded && logs && (
                    <>
                      <div 
                        className="fixed inset-0 bg-black/50 z-50"
                        onClick={() => setLogsExpanded(false)}
                      />
                      <div className="fixed inset-4 bg-background border border-border rounded-lg z-50 flex flex-col">
                        <div className="p-4 border-b border-border flex items-center justify-between">
                          <h3 className="font-medium">Job Logs</h3>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setLogsExpanded(false)}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                        <div className="flex-1 overflow-auto p-4">
                          <pre className="text-xs font-mono">
                            {logs}
                          </pre>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              )}
              
              {/* JSON Tab */}
              {activeTab === 'json' && (
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Raw job data (secrets redacted)
                    </p>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => copyToClipboard(JSON.stringify(job, null, 2), 'JSON')}
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy
                    </Button>
                  </div>
                  
                  <pre className="text-xs p-4 bg-muted/50 rounded-lg overflow-x-auto">
                    {JSON.stringify(job, null, 2)}
                  </pre>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </>
  )
}