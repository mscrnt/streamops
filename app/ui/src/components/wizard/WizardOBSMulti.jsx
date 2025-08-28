import { useState, useEffect, useCallback } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { 
  Video, 
  Check, 
  Plus
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { useApi } from '@/hooks/useApi'
import OBSConnectionModal from './OBSConnectionModal'
import OBSConnectionCard from './OBSConnectionCard'

export default function WizardOBSMulti({ data = [], onChange }) {
  const { api } = useApi()
  const [showModal, setShowModal] = useState(false)
  const [editingConnection, setEditingConnection] = useState(null)
  
  // Fetch OBS connections
  const { data: connections, isLoading, refetch } = useQuery({
    queryKey: ['obs', 'connections'],
    queryFn: async () => {
      console.log('[WizardOBSMulti] Fetching OBS connections...')
      try {
        const response = await api.get('/obs')
        console.log('[WizardOBSMulti] OBS connections:', response.data)
        return response.data
      } catch (error) {
        console.error('[WizardOBSMulti] Error fetching connections:', error)
        return []
      }
    },
    refetchInterval: 5000 // Refresh status every 5 seconds
  })
  
  // Test connection mutation
  const testMutation = useMutation({
    mutationFn: async (connectionId) => {
      const response = await api.post(`/obs/${connectionId}/test`)
      return response.data
    }
  })
  
  // Connect mutation
  const connectMutation = useMutation({
    mutationFn: async (connectionId) => {
      const response = await api.post(`/obs/${connectionId}/connect`)
      return response.data
    },
    onSuccess: () => refetch()
  })
  
  // Disconnect mutation
  const disconnectMutation = useMutation({
    mutationFn: async (connectionId) => {
      const response = await api.post(`/obs/${connectionId}/disconnect`)
      return response.data
    },
    onSuccess: () => refetch()
  })
  
  // Delete mutation
  const deleteMutation = useMutation({
    mutationFn: async (connectionId) => {
      const response = await api.delete(`/obs/${connectionId}`)
      return response.data
    },
    onSuccess: () => refetch()
  })
  
  // Update parent when connections change
  useEffect(() => {
    if (!connections || !onChange) return
    onChange(connections)
  }, [connections]) // Intentionally omit onChange to prevent loops
  
  const handleAddConnection = useCallback(() => {
    console.log('[WizardOBSMulti] Opening modal to add connection')
    setEditingConnection(null)
    setShowModal(true)
  }, [])
  
  const handleEditConnection = useCallback((connection) => {
    console.log('[WizardOBSMulti] Opening modal to edit connection:', connection.name)
    setEditingConnection(connection)
    setShowModal(true)
  }, [])
  
  const handleDeleteConnection = useCallback(async (connectionId) => {
    console.log('[WizardOBSMulti] Deleting connection:', connectionId)
    if (window.confirm('Are you sure you want to delete this connection?')) {
      try {
        await deleteMutation.mutateAsync(connectionId)
        console.log('[WizardOBSMulti] Connection deleted successfully')
      } catch (error) {
        console.error('[WizardOBSMulti] Error deleting connection:', error)
      }
    }
  }, [deleteMutation])
  
  const handleTestConnection = useCallback(async (connectionId) => {
    console.log('[WizardOBSMulti] Testing connection:', connectionId)
    try {
      const result = await testMutation.mutateAsync(connectionId)
      console.log('[WizardOBSMulti] Test result:', result)
      return result
    } catch (error) {
      console.error('[WizardOBSMulti] Test error:', error)
      throw error
    }
  }, [testMutation])
  
  const handleToggleConnection = useCallback(async (connection) => {
    console.log('[WizardOBSMulti] Toggling connection:', connection.name, 'from', connection.connected, 'to', !connection.connected)
    try {
      if (connection.connected) {
        await disconnectMutation.mutateAsync(connection.id)
        console.log('[WizardOBSMulti] Disconnected successfully')
      } else {
        await connectMutation.mutateAsync(connection.id)
        console.log('[WizardOBSMulti] Connected successfully')
      }
    } catch (error) {
      console.error('[WizardOBSMulti] Toggle error:', error)
    }
  }, [connectMutation, disconnectMutation])
  
  if (isLoading) {
    return (
      <Card>
        <CardContent className="py-8">
          <div className="flex items-center justify-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
          </div>
        </CardContent>
      </Card>
    )
  }
  
  return (
    <div className="space-y-6">
      {/* Info card */}
      <Card className="bg-muted/50">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Video className="h-5 w-5" />
            What OBS integration enables
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-success mt-0.5" />
            <div>
              <strong>Automatic recording detection</strong> — StreamOps waits a <strong>quiet period (default 45s)</strong> after recording/streaming <strong>stops</strong> before processing, so files are complete.
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-success mt-0.5" />
            <div>
              <strong>Scene change markers</strong> — We capture scene switches to help with edits.
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-success mt-0.5" />
            <div>
              <strong>Recording guardrails</strong> — Heavy jobs pause while any connected OBS is recording/streaming (configurable).
            </div>
          </div>
          <div className="flex items-start gap-2">
            <Check className="h-4 w-4 text-success mt-0.5" />
            <div>
              <strong>Session metadata</strong> — Profile, collection, and timing are attached to assets.
            </div>
          </div>
        </CardContent>
      </Card>
      
      {/* Connections list */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-medium">OBS Instances</h3>
          <Button onClick={handleAddConnection}>
            <Plus className="h-4 w-4 mr-2" />
            Add OBS Instance
          </Button>
        </div>
        
        {connections && connections.length > 0 ? (
          <div className="grid gap-4">
            {connections.map(connection => (
              <OBSConnectionCard 
                key={connection.id} 
                connection={connection}
                onTest={handleTestConnection}
                onToggle={handleToggleConnection}
                onEdit={handleEditConnection}
                onDelete={handleDeleteConnection}
                isToggling={connectMutation.isLoading || disconnectMutation.isLoading}
              />
            ))}
          </div>
        ) : (
          <Card className="border-dashed">
            <CardContent className="py-8">
              <div className="text-center space-y-3">
                <Video className="h-12 w-12 text-muted-foreground mx-auto" />
                <div>
                  <p className="font-medium">No OBS connections configured</p>
                  <p className="text-sm text-muted-foreground">
                    Add your first OBS instance to enable automatic recording detection
                  </p>
                </div>
                <Button onClick={handleAddConnection}>
                  <Plus className="h-4 w-4 mr-2" />
                  Add OBS Instance
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
      
      {/* Optional skip message */}
      {(!connections || connections.length === 0) && (
        <div className="text-center text-sm text-muted-foreground">
          OBS integration is optional. You can skip this step and configure it later.
        </div>
      )}
      
      {/* Connection modal */}
      <OBSConnectionModal
        open={showModal}
        onClose={() => {
          setShowModal(false)
          setEditingConnection(null)
        }}
        connection={editingConnection}
        onSave={() => {
          setShowModal(false)
          setEditingConnection(null)
          refetch()
        }}
      />
    </div>
  )
}