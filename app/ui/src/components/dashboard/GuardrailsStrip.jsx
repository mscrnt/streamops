import { useQuery } from '@tanstack/react-query'
import { Shield, AlertTriangle, CheckCircle, Cpu, HardDrive, Activity, Radio } from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { cn } from '@/lib/utils'

export default function GuardrailsStrip() {
  const { api } = useApi()
  
  // Fetch guardrails status
  const { data: status, isLoading } = useQuery({
    queryKey: ['guardrails', 'status'],
    queryFn: async () => {
      const response = await api.get('/guardrails/')
      return response.data
    },
    refetchInterval: 5000, // Check every 5 seconds
    staleTime: 2000
  })
  
  if (isLoading || !status) {
    return (
      <div className="bg-muted/50 border rounded-lg p-3 animate-pulse">
        <div className="h-5 bg-muted rounded w-48" />
      </div>
    )
  }
  
  const isActive = status.active
  const mainReason = status.reasons?.[0]
  
  return (
    <div className={cn(
      "border rounded-lg p-3 transition-colors",
      isActive ? "bg-warning/10 border-warning/30" : "bg-muted/30"
    )}>
      <div className="flex items-center justify-between">
        {/* Left side - Status */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <Shield className={cn(
              "w-4 h-4",
              isActive ? "text-warning" : "text-success"
            )} />
            <span className="font-medium text-sm">
              Guardrails
            </span>
            <Badge 
              variant={isActive ? "warning" : "success"}
              className="text-xs"
            >
              {isActive ? "Active" : "Clear"}
            </Badge>
          </div>
          
          {isActive && mainReason && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <AlertTriangle className="w-3 h-3" />
              <span>{mainReason}</span>
              {status.reasons.length > 1 && (
                <span>+{status.reasons.length - 1} more</span>
              )}
            </div>
          )}
        </div>
        
        {/* Right side - Metrics */}
        <div className="flex items-center gap-4 text-xs">
          {/* CPU */}
          <div className="flex items-center gap-1">
            <Cpu className={cn(
              "w-3 h-3",
              status.cpu_percent > (status.thresholds?.cpu_threshold_pct || 70) 
                ? "text-warning" 
                : "text-muted-foreground"
            )} />
            <span className={cn(
              status.cpu_percent > (status.thresholds?.cpu_threshold_pct || 70) 
                ? "text-warning font-medium" 
                : "text-muted-foreground"
            )}>
              {Math.round(status.cpu_percent)}%
            </span>
          </div>
          
          {/* Memory */}
          <div className="flex items-center gap-1">
            <Activity className={cn(
              "w-3 h-3",
              status.memory_available_gb < (status.thresholds?.min_memory_gb || 2)
                ? "text-warning" 
                : "text-muted-foreground"
            )} />
            <span className={cn(
              status.memory_available_gb < (status.thresholds?.min_memory_gb || 2)
                ? "text-warning font-medium" 
                : "text-muted-foreground"
            )}>
              {status.memory_available_gb?.toFixed(1)}GB
            </span>
          </div>
          
          {/* Disk */}
          <div className="flex items-center gap-1">
            <HardDrive className={cn(
              "w-3 h-3",
              status.disk_free_gb < (status.thresholds?.min_disk_gb || 10)
                ? "text-warning" 
                : "text-muted-foreground"
            )} />
            <span className={cn(
              status.disk_free_gb < (status.thresholds?.min_disk_gb || 10)
                ? "text-warning font-medium" 
                : "text-muted-foreground"
            )}>
              {Math.round(status.disk_free_gb)}GB
            </span>
          </div>
          
          {/* Recording */}
          {status.is_recording && (
            <div className="flex items-center gap-1">
              <Radio className="w-3 h-3 text-destructive animate-pulse" />
              <span className="text-destructive font-medium">REC</span>
            </div>
          )}
          
          {/* Streaming */}
          {status.is_streaming && (
            <div className="flex items-center gap-1">
              <Radio className="w-3 h-3 text-purple-500 animate-pulse" />
              <span className="text-purple-500 font-medium">LIVE</span>
            </div>
          )}
        </div>
      </div>
      
      {/* Expandable details on hover/click */}
      {isActive && status.reasons.length > 0 && (
        <details className="mt-2">
          <summary className="text-xs text-muted-foreground cursor-pointer hover:text-foreground">
            View all active guardrails ({status.reasons.length})
          </summary>
          <ul className="mt-2 space-y-1 text-xs">
            {status.reasons.map((reason, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-1 h-1 bg-warning rounded-full" />
                <span className="text-muted-foreground">{reason}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}