import { useState } from 'react'
import { 
  Play, 
  Pause, 
  Square, 
  RefreshCw, 
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertCircle,
  MoreHorizontal,
  Trash2,
  RotateCcw,
  PlayCircle,
  PauseCircle,
  FileText
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { SimpleSelect } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableSkeleton, TableEmpty } from '@/components/ui/Table'
import { 
  useJobs, 
  useActiveJobs, 
  useJobStats, 
  useCancelJob, 
  useRetryJob, 
  useBulkJobOperation,
  usePauseQueue,
  useResumeQueue,
  useClearQueue,
  useJobHistory
} from '@/hooks/useJobs'
import { useStore } from '@/store/useStore'
import { formatDuration, formatRelativeTime } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'
import toast from 'react-hot-toast'

export default function Jobs() {
  // Local state
  const [selectedJobs, setSelectedJobs] = useState([])
  const [showHistory, setShowHistory] = useState(false)
  
  // Store state
  const { jobFilters, setJobFilters } = useStore()
  
  // API hooks
  const { data: jobs, isLoading: jobsLoading, refetch: refetchJobs } = useJobs()
  const { data: activeJobs } = useActiveJobs()
  const { data: jobStats } = useJobStats()
  const { data: jobHistory } = useJobHistory()
  const cancelJob = useCancelJob()
  const retryJob = useRetryJob()
  const bulkOperation = useBulkJobOperation()
  const pauseQueue = usePauseQueue()
  const resumeQueue = useResumeQueue()
  const clearQueue = useClearQueue()

  // Data to display
  const displayData = showHistory ? jobHistory : jobs
  const totalActive = activeJobs?.length || 0
  const runningCount = activeJobs?.filter(job => job.status === 'running')?.length || 0
  const queuedCount = activeJobs?.filter(job => job.status === 'pending')?.length || 0

  const handleFilterChange = (key, value) => {
    setJobFilters({ [key]: value })
  }

  const handleSelectJob = (jobId) => {
    setSelectedJobs(prev => 
      prev.includes(jobId) 
        ? prev.filter(id => id !== jobId)
        : [...prev, jobId]
    )
  }

  const handleSelectAll = () => {
    if (selectedJobs.length === displayData?.length) {
      setSelectedJobs([])
    } else {
      setSelectedJobs(displayData?.map(job => job.id) || [])
    }
  }

  const handleBulkOperation = async (operation) => {
    if (selectedJobs.length === 0) {
      toast.error('No jobs selected')
      return
    }

    try {
      await bulkOperation.mutateAsync({
        operation,
        jobIds: selectedJobs
      })
      setSelectedJobs([])
    } catch (error) {
      toast.error(`Bulk ${operation} failed`)
    }
  }

  const handleDeleteJob = async (jobId) => {
    try {
      const response = await fetch(`/api/jobs/${jobId}`, {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' }
      })
      
      if (response.ok) {
        toast.success('Job deleted successfully')
        // Refresh job list
        refetchJobs()
      } else {
        toast.error('Failed to delete job')
      }
    } catch (error) {
      console.error('Failed to delete job:', error)
      toast.error('Failed to delete job')
    }
  }

  const fetchJobLogs = async (jobId) => {
    try {
      const response = await fetch(`/api/jobs/${jobId}/logs`)
      if (response.ok) {
        const logs = await response.json()
        // Handle logs display
        console.log('Job logs:', logs)
      }
    } catch (error) {
      console.error('Failed to fetch job logs:', error)
    }
  }

  const getJobIcon = (type) => {
    switch (type) {
      case 'remux':
        return RefreshCw
      case 'proxy':
        return Play
      case 'thumbnail':
        return FileText
      case 'transcode':
        return PlayCircle
      default:
        return PlayCircle
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'completed':
        return CheckCircle
      case 'failed':
        return XCircle
      case 'running':
        return Play
      case 'pending':
        return Clock
      case 'cancelled':
        return Square
      default:
        return AlertCircle
    }
  }

  const statusOptions = [
    { value: 'all', label: 'All Status' },
    { value: 'pending', label: 'Pending' },
    { value: 'running', label: 'Running' },
    { value: 'completed', label: 'Completed' },
    { value: 'failed', label: 'Failed' },
    { value: 'cancelled', label: 'Cancelled' },
  ]

  const typeOptions = [
    { value: 'all', label: 'All Types' },
    { value: 'remux', label: 'Remux' },
    { value: 'proxy', label: 'Proxy' },
    { value: 'thumbnail', label: 'Thumbnail' },
    { value: 'transcode', label: 'Transcode' },
    { value: 'index', label: 'Index' },
  ]

  const sortOptions = [
    { value: 'created_at', label: 'Created Date' },
    { value: 'updated_at', label: 'Updated Date' },
    { value: 'status', label: 'Status' },
    { value: 'type', label: 'Type' },
  ]

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Jobs</h1>
          <p className="text-muted-foreground">
            Monitor and manage processing jobs
          </p>
        </div>
        <div className="flex items-center space-x-2">
          <Button
            variant={showHistory ? 'outline' : 'default'}
            size="sm"
            onClick={() => setShowHistory(false)}
          >
            Active ({totalActive})
          </Button>
          <Button
            variant={showHistory ? 'default' : 'outline'}
            size="sm"
            onClick={() => setShowHistory(true)}
          >
            History
          </Button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Running Jobs</CardTitle>
            <Play className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{runningCount}</div>
            <p className="text-xs text-muted-foreground">
              Currently processing
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Queued Jobs</CardTitle>
            <Clock className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{queuedCount}</div>
            <p className="text-xs text-muted-foreground">
              Waiting to start
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed Today</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{jobStats?.completed || 0}</div>
            <p className="text-xs text-muted-foreground">
              Successfully finished
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Failed Today</CardTitle>
            <XCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{jobStats?.failed || 0}</div>
            <p className="text-xs text-muted-foreground">
              Requires attention
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Queue Controls */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <h3 className="font-medium">Queue Management</h3>
              <div className="flex items-center space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => pauseQueue.mutate()}
                  loading={pauseQueue.isLoading}
                >
                  <PauseCircle className="h-4 w-4 mr-1" />
                  Pause Queue
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => resumeQueue.mutate()}
                  loading={resumeQueue.isLoading}
                >
                  <PlayCircle className="h-4 w-4 mr-1" />
                  Resume Queue
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => {
                    if (confirm('Clear all pending jobs from the queue?')) {
                      clearQueue.mutate()
                    }
                  }}
                  loading={clearQueue.isLoading}
                >
                  Clear Queue
                </Button>
              </div>
            </div>
            
            <Button
              variant="outline"
              size="sm"
              onClick={() => refetchJobs()}
            >
              <RefreshCw className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="flex flex-col space-y-4 md:flex-row md:space-y-0 md:space-x-4">
            <SimpleSelect
              options={statusOptions}
              value={jobFilters.status}
              onValueChange={(value) => handleFilterChange('status', value)}
              placeholder="Filter by Status"
            />
            
            <SimpleSelect
              options={typeOptions}
              value={jobFilters.type}
              onValueChange={(value) => handleFilterChange('type', value)}
              placeholder="Filter by Type"
            />
            
            <SimpleSelect
              options={sortOptions}
              value={jobFilters.sortBy}
              onValueChange={(value) => handleFilterChange('sortBy', value)}
              placeholder="Sort By"
            />
          </div>

          {/* Bulk Actions */}
          {selectedJobs.length > 0 && (
            <div className="flex items-center justify-between mt-4 p-3 bg-muted rounded-lg">
              <span className="text-sm font-medium">
                {selectedJobs.length} job{selectedJobs.length > 1 ? 's' : ''} selected
              </span>
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkOperation('cancel')}
                >
                  Cancel
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleBulkOperation('retry')}
                >
                  Retry
                </Button>
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => handleBulkOperation('delete')}
                >
                  Delete
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Jobs Table */}
      <Card>
        <CardHeader>
          <CardTitle>
            {showHistory ? 'Job History' : 'Active Jobs'}
          </CardTitle>
          <CardDescription>
            {showHistory 
              ? 'Recently completed and failed jobs' 
              : 'Currently running and queued jobs'
            }
          </CardDescription>
        </CardHeader>
        <CardContent>
          {jobsLoading ? (
            <TableSkeleton rows={10} columns={7} />
          ) : !displayData || displayData.length === 0 ? (
            <TableEmpty
              icon={PlayCircle}
              title={showHistory ? 'No job history' : 'No active jobs'}
              description={showHistory 
                ? 'Completed jobs will appear here' 
                : 'Jobs will appear here when they are created'
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      checked={selectedJobs.length === displayData.length}
                      onChange={handleSelectAll}
                      className="rounded border-border"
                    />
                  </TableHead>
                  <TableHead>Job</TableHead>
                  <TableHead>Asset</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Progress</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayData.map((job) => {
                  const JobIcon = getJobIcon(job.type)
                  const StatusIcon = getStatusIcon(job.status)
                  const isSelected = selectedJobs.includes(job.id)
                  const duration = job.completed_at 
                    ? new Date(job.completed_at) - new Date(job.started_at || job.created_at)
                    : job.started_at 
                      ? Date.now() - new Date(job.started_at)
                      : null
                  
                  return (
                    <TableRow 
                      key={job.id}
                      className={isSelected ? 'bg-muted/50' : ''}
                    >
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleSelectJob(job.id)}
                          className="rounded border-border"
                        />
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-3">
                          <JobIcon className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">{job.type}</p>
                            <p className="text-xs text-muted-foreground">
                              ID: {job.id ? job.id.slice(0, 8) : 'N/A'}
                            </p>
                          </div>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="min-w-0">
                          <p className="truncate max-w-48 text-sm">
                            {job.asset_path || job.asset_id || 'Unknown'}
                          </p>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          <StatusIcon className={`h-4 w-4 ${
                            job.status === 'completed' ? 'text-green-500' :
                            job.status === 'failed' ? 'text-red-500' :
                            job.status === 'running' ? 'text-blue-500' :
                            job.status === 'pending' ? 'text-yellow-500' :
                            'text-gray-500'
                          }`} />
                          <StatusBadge status={job.status} />
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        {job.progress !== null && job.progress !== undefined ? (
                          <div className="flex items-center space-x-2">
                            <div className="w-20 h-2 bg-muted rounded-full">
                              <div 
                                className="h-2 bg-primary rounded-full transition-all" 
                                style={{ width: `${job.progress}%` }}
                              />
                            </div>
                            <span className="text-xs">{job.progress}%</span>
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">N/A</span>
                        )}
                      </TableCell>
                      
                      <TableCell className="text-sm text-muted-foreground">
                        {duration ? formatDuration(Math.floor(duration / 1000)) : 'N/A'}
                      </TableCell>
                      
                      <TableCell className="text-sm text-muted-foreground">
                        {formatRelativeTime(job.created_at)}
                      </TableCell>
                      
                      <TableCell>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="sm">
                              <MoreHorizontal className="h-4 w-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent 
                            align="end"
                            className="w-40 bg-popover border border-border rounded-md shadow-lg p-1"
                          >
                            {(job.status === 'running' || job.status === 'pending') && (
                              <DropdownMenuItem 
                                className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                                onClick={() => cancelJob.mutate(job.id)}
                              >
                                <Square className="h-4 w-4 mr-2" />
                                Cancel
                              </DropdownMenuItem>
                            )}
                            
                            {job.status === 'failed' && (
                              <DropdownMenuItem 
                                className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                                onClick={() => retryJob.mutate(job.id)}
                              >
                                <RotateCcw className="h-4 w-4 mr-2" />
                                Retry
                              </DropdownMenuItem>
                            )}
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                // Implement log viewer
                                setSelectedJob(job);
                                setShowLogViewer(true);
                                fetchJobLogs(job.id);
                                toast.info('Log viewer coming soon')
                              }}
                            >
                              <FileText className="h-4 w-4 mr-2" />
                              View Logs
                            </DropdownMenuItem>
                            
                            <DropdownMenuSeparator className="h-px bg-border my-1" />
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-destructive hover:text-destructive-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                if (window.confirm(`Delete job ${job.id}?`)) {
                                  handleDeleteJob(job.id);
                                }
                              }}
                            >
                              <Trash2 className="h-4 w-4 mr-2" />
                              Delete
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}