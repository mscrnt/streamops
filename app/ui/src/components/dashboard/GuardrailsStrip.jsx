import { 
  Shield, 
  ShieldOff,
  Wifi, 
  WifiOff,
  Video,
  VideoOff,
  AlertTriangle,
  Settings,
  Activity,
  Cpu,
  Zap,
  PauseCircle,
  PlayCircle
} from 'lucide-react'
import { Badge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/Tooltip'

export default function GuardrailsStrip({ guardrails, obs, onManageOBS }) {
  // Determine guardrails status
  const isGuardrailsActive = guardrails?.active || false
  const guardrailReason = guardrails?.reason || null
  
  // Determine OBS status
  const isOBSConnected = obs?.connected || false
  const isRecording = obs?.recording || false
  const obsVersion = obs?.version || null
  
  // Get guardrail icon and color
  const getGuardrailStatus = () => {
    if (!isGuardrailsActive) {
      return {
        icon: Shield,
        color: 'text-green-500',
        bgColor: 'bg-green-500/10',
        borderColor: 'border-green-500/20',
        label: 'Guardrails Inactive',
        description: 'Processing running normally'
      }
    }
    
    // Parse the reason to determine which guardrail is active
    if (guardrailReason?.includes('recording')) {
      return {
        icon: Video,
        color: 'text-yellow-500',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/20',
        label: 'Recording Guardrail',
        description: 'Processing paused during recording'
      }
    } else if (guardrailReason?.includes('CPU')) {
      return {
        icon: Cpu,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500/20',
        label: 'CPU Guardrail',
        description: guardrailReason
      }
    } else if (guardrailReason?.includes('GPU')) {
      return {
        icon: Zap,
        color: 'text-orange-500',
        bgColor: 'bg-orange-500/10',
        borderColor: 'border-orange-500/20',
        label: 'GPU Guardrail',
        description: guardrailReason
      }
    } else {
      return {
        icon: ShieldOff,
        color: 'text-yellow-500',
        bgColor: 'bg-yellow-500/10',
        borderColor: 'border-yellow-500/20',
        label: 'Guardrail Active',
        description: guardrailReason || 'Processing temporarily paused'
      }
    }
  }
  
  const guardrailStatus = getGuardrailStatus()
  const GuardrailIcon = guardrailStatus.icon
  
  return (
    <div className={`flex items-center justify-between p-3 rounded-lg border ${guardrailStatus.borderColor} ${guardrailStatus.bgColor}`}>
      <div className="flex items-center space-x-4">
        {/* Guardrails Status */}
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center space-x-2">
                <div className={`p-2 rounded-lg ${guardrailStatus.bgColor}`}>
                  <GuardrailIcon className={`h-4 w-4 ${guardrailStatus.color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium">{guardrailStatus.label}</p>
                  <p className="text-xs text-muted-foreground">
                    {guardrailStatus.description}
                  </p>
                </div>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p>Guardrails automatically pause processing to protect system resources</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
        
        {/* Divider */}
        <div className="h-8 w-px bg-border" />
        
        {/* OBS Status */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            {isOBSConnected ? (
              <>
                <Wifi className="h-4 w-4 text-green-500" />
                <span className="text-sm">OBS Connected</span>
                {obsVersion && (
                  <Badge variant="outline" className="text-xs">
                    v{obsVersion}
                  </Badge>
                )}
              </>
            ) : (
              <>
                <WifiOff className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm text-muted-foreground">OBS Disconnected</span>
              </>
            )}
          </div>
          
          {isOBSConnected && (
            <div className="flex items-center space-x-2">
              {isRecording ? (
                <>
                  <div className="flex items-center space-x-1">
                    <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
                    <span className="text-sm font-medium text-red-500">Recording</span>
                  </div>
                  <Badge variant="destructive" className="text-xs">
                    LIVE
                  </Badge>
                </>
              ) : (
                <div className="flex items-center space-x-1">
                  <VideoOff className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm text-muted-foreground">Not Recording</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      
      {/* Actions */}
      <div className="flex items-center space-x-2">
        {isGuardrailsActive && (
          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <div className="flex items-center space-x-1 px-2 py-1 rounded bg-yellow-500/20">
                  <PauseCircle className="h-3 w-3 text-yellow-500" />
                  <span className="text-xs font-medium text-yellow-500">
                    Processing Paused
                  </span>
                </div>
              </TooltipTrigger>
              <TooltipContent>
                <p>Jobs will resume when guardrail conditions clear</p>
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        )}
        
        {!isOBSConnected && (
          <Button
            variant="outline"
            size="sm"
            onClick={onManageOBS}
          >
            <Settings className="h-4 w-4 mr-1" />
            Connect OBS
          </Button>
        )}
        
        {isOBSConnected && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onManageOBS}
          >
            <Settings className="h-4 w-4" />
          </Button>
        )}
      </div>
    </div>
  )
}