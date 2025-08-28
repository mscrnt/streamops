import { useState } from 'react'
import { 
  Wifi,
  WifiOff,
  Eye,
  EyeOff,
  TestTube,
  Plus,
  Edit,
  Trash2,
  MoreVertical,
  Clock,
  Circle,
  RefreshCw,
  Check,
  X,
  AlertCircle
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import { cn, formatDistanceToNow } from '@/lib/utils'

export default function OBSConnectionCard({ 
  connection, 
  onTest, 
  onToggle, 
  onEdit, 
  onDelete,
  isToggling = false 
}) {
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState(null)
  
  const handleTest = async () => {
    console.log('[OBSConnectionCard] Test clicked for:', connection.name)
    setTesting(true)
    setTestResult(null)
    try {
      const result = await onTest(connection.id)
      setTestResult(result)
    } catch (error) {
      console.error('[OBSConnectionCard] Test error:', error)
      setTestResult({ ok: false, error: error.message })
    } finally {
      setTesting(false)
    }
  }

  const handleToggle = () => {
    console.log('[OBSConnectionCard] Toggle clicked for:', connection.name)
    onToggle(connection)
  }

  const handleEdit = () => {
    console.log('[OBSConnectionCard] Edit clicked for:', connection.name)
    onEdit(connection)
  }

  const handleDelete = () => {
    console.log('[OBSConnectionCard] Delete clicked for:', connection.name)
    onDelete(connection.id)
  }
  
  const getStatusColor = (status) => {
    if (!status) return 'secondary'
    if (status === 'connected') return 'success'
    if (status.startsWith('error')) return 'destructive'
    return 'secondary'
  }
  
  const getStatusIcon = () => {
    if (connection.connected) {
      if (connection.recording) {
        return <Circle className="w-3 h-3 text-red-500 fill-red-500 animate-pulse" />
      }
      if (connection.streaming) {
        return <Circle className="w-3 h-3 text-blue-500 fill-blue-500 animate-pulse" />
      }
      return <Wifi className="w-3 h-3 text-success" />
    }
    return <WifiOff className="w-3 h-3 text-muted-foreground" />
  }
  
  return (
    <Card className={cn(
      "transition-all",
      connection.connected && "border-success/50"
    )}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-lg flex items-center gap-2">
              {connection.name}
              {getStatusIcon()}
            </CardTitle>
            <div className="text-sm text-muted-foreground mt-1">
              {connection.ws_url}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleToggle}
              disabled={isToggling}
            >
              {connection.connected ? (
                <WifiOff className="h-4 w-4" />
              ) : (
                <Wifi className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleEdit}
            >
              <Edit className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleDelete}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Status badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge variant={getStatusColor(connection.last_status)}>
            {connection.connected ? 'Connected' : 'Disconnected'}
          </Badge>
          
          {connection.recording && (
            <Badge variant="destructive">Recording</Badge>
          )}
          
          {connection.streaming && (
            <Badge variant="info">Streaming</Badge>
          )}
          
          {connection.current_scene && (
            <Badge variant="outline">Scene: {connection.current_scene}</Badge>
          )}
          
          {connection.auto_connect && (
            <Badge variant="secondary">Auto-connect</Badge>
          )}
          
          {connection.roles && connection.roles.length > 0 && (
            <>
              {connection.roles.map(role => (
                <Badge key={role} variant="outline">
                  {role}
                </Badge>
              ))}
            </>
          )}
        </div>
        
        {/* Last seen */}
        {connection.last_seen_ts && (
          <div className="text-xs text-muted-foreground flex items-center gap-1">
            <Clock className="w-3 h-3" />
            Last seen {formatDistanceToNow(new Date(connection.last_seen_ts))} ago
          </div>
        )}
        
        {/* Test connection */}
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testing}
          >
            {testing ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Testing...
              </>
            ) : (
              <>
                <TestTube className="h-4 w-4 mr-2" />
                Test Connection
              </>
            )}
          </Button>
          
          {testResult && (
            <div className="flex-1">
              {testResult.ok ? (
                <div className="text-sm text-success flex items-center gap-1">
                  <Check className="w-3 h-3" />
                  {testResult.message || `Connected to OBS ${testResult.obs_version}`}
                </div>
              ) : (
                <div className="text-sm text-destructive flex items-center gap-1">
                  <X className="w-3 h-3" />
                  {testResult.error || 'Connection failed'}
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* Last error */}
        {connection.last_error && !connection.connected && (
          <div className="p-2 bg-destructive/10 rounded-md">
            <div className="text-sm text-destructive flex items-start gap-2">
              <AlertCircle className="w-4 h-4 mt-0.5" />
              <span>{connection.last_error}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}