import { AlertCircle, CheckCircle, Activity, Cpu, MemoryStick, Shield } from 'lucide-react'
import { formatBytes } from '@/lib/utils'
import { useSystem } from '@/hooks/useSystem'
import { useJobs } from '@/hooks/useJobs'
import { useState, useEffect } from 'react'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'

export default function TopbarMetrics() {
  const { data: systemData, isLoading: systemLoading } = useSystem()
  const { data: jobsData } = useJobs({ state: 'running,queued' })
  
  const activeJobsCount = jobsData?.jobs?.filter(j => j.state === 'running').length || 0
  const queuedJobsCount = jobsData?.jobs?.filter(j => j.state === 'queued').length || 0
  
  // Determine guardrails status
  const guardrails = systemData?.guardrails || {}
  const isGuardrailsPaused = guardrails.active || false
  
  const getGuardrailsReasons = () => {
    // If there's a single reason string, return it as an array
    if (guardrails.reason) {
      return [guardrails.reason]
    }
    
    // Otherwise check individual flags (legacy format)
    const reasons = []
    if (guardrails.recording) reasons.push('Recording active')
    if (guardrails.streaming) reasons.push('Streaming active')
    if (guardrails.cpu_high) reasons.push(`CPU high (${systemData?.cpu?.percent || 0}%)`)
    if (guardrails.gpu_high) reasons.push(`GPU high (${systemData?.gpu?.percent || 0}%)`)
    if (guardrails.disk_space_low) reasons.push('Disk space low')
    return reasons
  }
  
  // Determine system health
  const getSystemHealth = () => {
    if (systemLoading) return { status: 'loading', color: 'text-muted-foreground' }
    if (!systemData) return { status: 'unknown', color: 'text-muted-foreground' }
    
    // Check for critical issues
    if (guardrails.disk_space_low) return { status: 'Critical', color: 'text-red-500' }
    if (systemData?.health?.status === 'critical') return { status: 'Critical', color: 'text-red-500' }
    
    // Check for warnings
    if (guardrails.cpu_high || guardrails.gpu_high) return { status: 'Degraded', color: 'text-yellow-500' }
    if (systemData?.health?.status === 'warning') return { status: 'Degraded', color: 'text-yellow-500' }
    
    return { status: 'Healthy', color: 'text-green-500' }
  }
  
  const health = getSystemHealth()
  
  return (
    <div className="sticky top-0 z-40 bg-background border-b px-4 h-14 flex items-center justify-between shadow-sm">
      <div className="flex items-center gap-4">
        {/* Guardrails Badge */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className={`flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium cursor-help transition-colors ${
                isGuardrailsPaused ? 'bg-amber-100 text-amber-700 dark:bg-amber-950/50 dark:text-amber-300' : 
                                     'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300'
              }`}>
                <Shield className="h-4 w-4" />
                {isGuardrailsPaused ? (
                  <span>Guardrails Active</span>
                ) : (
                  <span>Safe</span>
                )}
              </div>
            </TooltipTrigger>
            <TooltipContent className="max-w-xs">
              <div className="space-y-2">
                {isGuardrailsPaused ? (
                  <>
                    <p className="font-semibold text-foreground">Guardrails Active</p>
                    <p className="text-sm">
                      Automatic processing is paused to protect system performance during:
                    </p>
                    <div className="space-y-1">
                      {getGuardrailsReasons().map((reason, i) => (
                        <p key={i} className="text-sm font-medium">• {reason}</p>
                      ))}
                    </div>
                    <p className="text-sm mt-2">
                      Processing will resume automatically when conditions clear.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-semibold text-foreground">System Safe</p>
                    <p className="text-sm">
                      No active guardrails. Automatic processing is enabled.
                    </p>
                    <div className="mt-2">
                      <p className="text-sm font-medium">
                        Guardrails activate automatically when:
                      </p>
                      <ul className="text-sm mt-1 space-y-0.5">
                        <li>• OBS is recording or streaming</li>
                        <li>• CPU usage exceeds 70%</li>
                        <li>• GPU usage exceeds 40%</li>
                        <li>• Disk space is critically low</li>
                      </ul>
                    </div>
                  </>
                )}
              </div>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        
        {/* KPI Pills */}
        <div className="flex items-center gap-3">
          {/* Active Jobs */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium bg-muted/50 cursor-help">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                  <span>{activeJobsCount} Active</span>
                  {queuedJobsCount > 0 && (
                    <span className="text-muted-foreground">({queuedJobsCount} queued)</span>
                  )}
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-semibold">Processing Jobs</p>
                <p className="text-sm">Currently running media processing tasks</p>
                {queuedJobsCount > 0 && (
                  <p className="text-sm mt-1">{queuedJobsCount} jobs waiting in queue</p>
                )}
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          
          {/* CPU */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium bg-muted/50 cursor-help">
                  <Cpu className="h-4 w-4 text-muted-foreground" />
                  <span>{Math.round(systemData?.cpu?.percent || 0)}% CPU</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-semibold">CPU Usage</p>
                <p className="text-sm">Current processor utilization</p>
                <p className="text-sm mt-1">Processing pauses above 70%</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
          
          {/* GPU */}
          {systemData?.gpu?.present && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium bg-muted/50 cursor-help">
                    <i className="fa-solid fa-microchip text-muted-foreground" style={{ fontSize: '14px' }}></i>
                    <span>{Math.round(systemData?.gpu?.percent || 0)}% GPU</span>
                  </div>
                </TooltipTrigger>
                <TooltipContent>
                  <p className="font-semibold">GPU Usage</p>
                  <p className="text-sm">Graphics card utilization</p>
                  <p className="text-sm mt-1">Processing pauses above 40%</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
          
          {/* Memory */}
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium bg-muted/50 cursor-help">
                  <MemoryStick className="h-4 w-4 text-muted-foreground" />
                  <span>{Math.round(systemData?.memory?.percent || 0)}% Memory</span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p className="font-semibold">RAM Usage</p>
                <p className="text-sm">System memory utilization</p>
                <p className="text-sm mt-1">{formatBytes(systemData?.memory?.used || 0)} of {formatBytes(systemData?.memory?.total || 0)}</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>
      
      {/* Right side - System Health */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <span className={`text-sm font-medium ${health.color}`}>
            System {health.status}
          </span>
        </div>
      </div>
    </div>
  )
}