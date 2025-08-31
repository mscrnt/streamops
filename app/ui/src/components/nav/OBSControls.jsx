import { useState, useEffect } from 'react'
import { Play, Square, Radio, Wifi, WifiOff, AlertCircle } from 'lucide-react'
import Button from '@/components/ui/Button'
import { useApi } from '@/hooks/useApi'
import { useQuery, useMutation } from '@tanstack/react-query'
import toast from 'react-hot-toast'

export default function OBSControls() {
  const { api } = useApi()
  const [expandedClient, setExpandedClient] = useState(null)

  // Fetch OBS clients status
  const { data: obsStatus, isLoading, refetch } = useQuery({
    queryKey: ['obs', 'status'],
    queryFn: async () => {
      const response = await api.get('/obs/status')
      return response.data
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  // Start recording mutation
  const startRecording = useMutation({
    mutationFn: async (clientName) => {
      const response = await api.post(`/obs/clients/${encodeURIComponent(clientName)}/recording/start`)
      return response.data
    },
    onSuccess: (data, clientName) => {
      toast.success(`Recording started on ${clientName}`)
      refetch()
    },
    onError: (error, clientName) => {
      toast.error(`Failed to start recording on ${clientName}: ${error.message}`)
    },
  })

  // Stop recording mutation
  const stopRecording = useMutation({
    mutationFn: async (clientName) => {
      const response = await api.post(`/obs/clients/${encodeURIComponent(clientName)}/recording/stop`)
      return response.data
    },
    onSuccess: (data, clientName) => {
      toast.success(`Recording stopped on ${clientName}`)
      refetch()
    },
    onError: (error, clientName) => {
      toast.error(`Failed to stop recording on ${clientName}: ${error.message}`)
    },
  })

  // Start streaming mutation
  const startStreaming = useMutation({
    mutationFn: async (clientName) => {
      const response = await api.post(`/obs/clients/${encodeURIComponent(clientName)}/streaming/start`)
      return response.data
    },
    onSuccess: (data, clientName) => {
      toast.success(`Streaming started on ${clientName}`)
      refetch()
    },
    onError: (error, clientName) => {
      toast.error(`Failed to start streaming on ${clientName}: ${error.message}`)
    },
  })

  // Stop streaming mutation
  const stopStreaming = useMutation({
    mutationFn: async (clientName) => {
      const response = await api.post(`/obs/clients/${encodeURIComponent(clientName)}/streaming/stop`)
      return response.data
    },
    onSuccess: (data, clientName) => {
      toast.success(`Streaming stopped on ${clientName}`)
      refetch()
    },
    onError: (error, clientName) => {
      toast.error(`Failed to stop streaming on ${clientName}: ${error.message}`)
    },
  })

  const clients = obsStatus?.connections || obsStatus?.clients || []
  const connectedClients = clients.filter(c => c.connected)

  if (isLoading) {
    return (
      <div className="px-3 py-4">
        <div className="text-xs text-muted-foreground">Loading OBS clients...</div>
      </div>
    )
  }

  if (connectedClients.length === 0) {
    return (
      <div className="px-3 py-4 border-t">
        <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
          OBS Controls
        </h2>
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <WifiOff className="h-4 w-4" />
          <span>No OBS instances connected</span>
        </div>
      </div>
    )
  }

  return (
    <div className="px-3 py-4 border-t">
      <h2 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-3">
        OBS Controls
      </h2>
      
      <div className="space-y-2">
        {connectedClients.map((client) => (
          <div key={client.name} className="rounded-lg border bg-card/50 p-2">
            {/* Client Header */}
            <div 
              className="flex items-center justify-between cursor-pointer"
              onClick={() => setExpandedClient(expandedClient === client.name ? null : client.name)}
            >
              <div className="flex items-center gap-2">
                <Wifi className="h-3.5 w-3.5 text-green-500" />
                <span className="text-sm font-medium">{client.name}</span>
              </div>
              <div className="flex items-center gap-1">
                {client.recording && (
                  <div className="flex items-center gap-1">
                    <div className="h-2 w-2 bg-red-500 rounded-full animate-pulse" />
                    <span className="text-xs text-red-500">REC</span>
                  </div>
                )}
                {client.streaming && (
                  <div className="flex items-center gap-1">
                    <div className="h-2 w-2 bg-blue-500 rounded-full animate-pulse" />
                    <span className="text-xs text-blue-500">LIVE</span>
                  </div>
                )}
              </div>
            </div>

            {/* Expanded Controls */}
            {expandedClient === client.name && (
              <div className="mt-3 pt-3 border-t space-y-2">
                {/* Recording Controls */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-16">Record:</span>
                  {client.recording ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      className="flex-1"
                      onClick={() => stopRecording.mutate(client.name)}
                      disabled={stopRecording.isPending}
                    >
                      <Square className="h-3.5 w-3.5 mr-1" />
                      Stop
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="default"
                      className="flex-1"
                      onClick={() => startRecording.mutate(client.name)}
                      disabled={startRecording.isPending}
                    >
                      <Play className="h-3.5 w-3.5 mr-1" />
                      Start
                    </Button>
                  )}
                </div>

                {/* Streaming Controls */}
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground w-16">Stream:</span>
                  {client.streaming ? (
                    <Button
                      size="sm"
                      variant="destructive"
                      className="flex-1"
                      onClick={() => stopStreaming.mutate(client.name)}
                      disabled={stopStreaming.isPending}
                    >
                      <Square className="h-3.5 w-3.5 mr-1" />
                      Stop
                    </Button>
                  ) : (
                    <Button
                      size="sm"
                      variant="secondary"
                      className="flex-1"
                      onClick={() => startStreaming.mutate(client.name)}
                      disabled={startStreaming.isPending}
                    >
                      <Radio className="h-3.5 w-3.5 mr-1" />
                      Go Live
                    </Button>
                  )}
                </div>

                {/* Recording Stats */}
                {client.recording && client.recording_duration && (
                  <div className="text-xs text-muted-foreground pt-1">
                    Recording: {formatDuration(client.recording_duration)}
                  </div>
                )}
                
                {/* Current Scene */}
                {client.current_scene && (
                  <div className="text-xs text-muted-foreground">
                    Scene: {client.current_scene}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Quick Actions for All */}
      {connectedClients.length > 1 && (
        <div className="mt-3 pt-3 border-t">
          <div className="text-xs text-muted-foreground mb-2">All Instances</div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                connectedClients.forEach(client => {
                  if (!client.recording) {
                    startRecording.mutate(client.name)
                  }
                })
              }}
            >
              <Play className="h-3.5 w-3.5 mr-1" />
              All Rec
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                connectedClients.forEach(client => {
                  if (client.recording) {
                    stopRecording.mutate(client.name)
                  }
                })
              }}
            >
              <Square className="h-3.5 w-3.5 mr-1" />
              Stop All
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}

function formatDuration(seconds) {
  if (!seconds) return '00:00:00'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)
  return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}