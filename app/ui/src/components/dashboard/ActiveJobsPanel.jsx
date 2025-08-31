import { useState } from 'react'
import { MoreVertical, Pause, Play, X, RefreshCw, FileVideo, Image, Archive, Settings } from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import Button from '@/components/ui/Button'
import { Checkbox } from '@/components/ui/Checkbox'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useJobs } from '@/hooks/useJobs'
import { useJobActions } from '@/hooks/useJobActions'
import { Link } from 'react-router-dom'

export default function ActiveJobsPanel() {
  const { data, isLoading, refetch } = useJobs({ 
    state: 'running,queued',
    limit: 100 
  })
  const { pauseJob, resumeJob, cancelJob } = useJobActions()
  const [selectedJobs, setSelectedJobs] = useState(new Set())
  
  const activeJobs = data?.jobs || []
  
  const getJobIcon = (type) => {
    switch(type) {
      case 'transcode':
      case 'remux':
        return <FileVideo className="h-4 w-4" />
      case 'thumbnail':
        return <Image className="h-4 w-4" />
      case 'archive':
        return <Archive className="h-4 w-4" />
      default:
        return <Settings className="h-4 w-4" />
    }
  }
  
  const getStatusPill = (state) => {
    const classes = {
      running: 'bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300',
      queued: 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300',
      paused: 'bg-gray-100 text-gray-700 dark:bg-gray-950/50 dark:text-gray-300',
    }
    return (
      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${classes[state] || classes.queued}`}>
        {state}
      </span>
    )
  }
  
  const toggleJobSelection = (jobId) => {
    const newSelection = new Set(selectedJobs)
    if (newSelection.has(jobId)) {
      newSelection.delete(jobId)
    } else {
      newSelection.add(jobId)
    }
    setSelectedJobs(newSelection)
  }
  
  const toggleAllSelection = () => {
    if (selectedJobs.size === activeJobs.length) {
      setSelectedJobs(new Set())
    } else {
      setSelectedJobs(new Set(activeJobs.map(j => j.id)))
    }
  }
  
  const formatETA = (job) => {
    if (job.state !== 'running' || !job.started_at) return null
    if (job.progress > 0 && job.progress < 100) {
      // Estimate based on progress
      const elapsed = Date.now() - new Date(job.started_at).getTime()
      const totalTime = elapsed / (job.progress / 100)
      const remaining = totalTime - elapsed
      if (remaining > 0) {
        const mins = Math.floor(remaining / 60000)
        return `~${mins}m left`
      }
    }
    return formatDistanceToNow(new Date(job.started_at), { addSuffix: false })
  }
  
  return (
    <div className="rounded-lg border bg-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h3 className="text-sm font-semibold">Active Jobs</h3>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => refetch()}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
          <Link to="/jobs?state=running,queued">
            <Button variant="ghost" size="sm">
              View All
            </Button>
          </Link>
        </div>
      </div>
      
      {/* Content with internal scroll */}
      <div className="h-[360px] overflow-y-auto scrollbar-thin">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <div className="animate-pulse text-sm text-muted-foreground">Loading jobs...</div>
          </div>
        ) : activeJobs.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <Settings className="h-8 w-8 text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              No active jobs — new recordings will trigger automatic processing.
            </p>
          </div>
        ) : (
          <div className="divide-y">
            {/* Select all row */}
            {activeJobs.length > 1 && (
              <div className="flex items-center gap-3 px-4 py-2 bg-muted/30">
                <Checkbox
                  checked={selectedJobs.size === activeJobs.length}
                  onCheckedChange={toggleAllSelection}
                />
                <span className="text-xs text-muted-foreground">
                  Select all ({activeJobs.length})
                </span>
              </div>
            )}
            
            {/* Job rows */}
            {activeJobs.map((job) => (
              <div key={job.id} className="flex items-center gap-3 px-4 py-2 hover:bg-muted/30">
                <Checkbox
                  checked={selectedJobs.has(job.id)}
                  onCheckedChange={() => toggleJobSelection(job.id)}
                />
                
                {getJobIcon(job.type)}
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium truncate">
                      {job.asset_name || job.input_path?.split('/').pop() || 'Unknown'}
                    </span>
                    {getStatusPill(job.state)}
                  </div>
                  
                  {job.state === 'running' && job.progress !== undefined && (
                    <div className="flex items-center gap-2 mt-1">
                      <div className="flex-1 bg-secondary rounded-full h-1.5">
                        <div 
                          className="h-1.5 rounded-full bg-primary transition-all"
                          style={{ width: `${Math.min(job.progress, 100)}%` }}
                        />
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {Math.round(job.progress)}%
                      </span>
                    </div>
                  )}
                  
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">
                      {job.type}
                    </span>
                    {formatETA(job) && (
                      <>
                        <span className="text-xs text-muted-foreground">•</span>
                        <span className="text-xs text-muted-foreground">
                          {formatETA(job)}
                        </span>
                      </>
                    )}
                  </div>
                </div>
                
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="icon" className="h-8 w-8">
                      <MoreVertical className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    {job.state === 'running' && (
                      <DropdownMenuItem onClick={() => pauseJob.mutate(job.id)}>
                        <Pause className="mr-2 h-4 w-4" />
                        Pause
                      </DropdownMenuItem>
                    )}
                    {job.state === 'paused' && (
                      <DropdownMenuItem onClick={() => resumeJob.mutate(job.id)}>
                        <Play className="mr-2 h-4 w-4" />
                        Resume
                      </DropdownMenuItem>
                    )}
                    <DropdownMenuItem onClick={() => cancelJob.mutate(job.id)}>
                      <X className="mr-2 h-4 w-4" />
                      Cancel
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}