import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogFooter,
  DialogDescription 
} from '@/components/ui/Dialog'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Label from '@/components/ui/Label'
import Checkbox from '@/components/ui/Checkbox'
import { useApi } from '@/hooks/useApi'
import { 
  Video, 
  Eye,
  EyeOff,
  TestTube,
  Check,
  X,
  AlertCircle,
  RefreshCw
} from 'lucide-react'

export default function OBSConnectionModal({ 
  open, 
  onClose, 
  connection = null,
  onSave 
}) {
  const { api } = useApi()
  const isEditing = !!connection
  
  const [formData, setFormData] = useState({
    name: '',
    ws_url: 'ws://host.docker.internal:4455',
    password: '',
    auto_connect: true,
    roles: []
  })
  
  const [showPassword, setShowPassword] = useState(false)
  const [testResult, setTestResult] = useState(null)
  const [testing, setTesting] = useState(false)
  
  // Reset form when modal opens/closes
  useEffect(() => {
    if (open) {
      if (connection) {
        // Editing existing connection
        setFormData({
          name: connection.name || '',
          ws_url: connection.ws_url || '',
          password: '', // Don't pre-fill password for security
          auto_connect: connection.auto_connect !== false,
          roles: connection.roles || []
        })
      } else {
        // New connection
        setFormData({
          name: '',
          ws_url: 'ws://host.docker.internal:4455',
          password: '',
          auto_connect: true,
          roles: []
        })
      }
      setTestResult(null)
      setShowPassword(false)
    }
  }, [open, connection])
  
  // Create mutation
  const createMutation = useMutation({
    mutationFn: async (data) => {
      const response = await api.post('/obs', data)
      return response.data
    },
    onSuccess: () => {
      onSave()
    }
  })
  
  // Update mutation
  const updateMutation = useMutation({
    mutationFn: async ({ id, data }) => {
      const response = await api.put(`/obs/${id}`, data)
      return response.data
    },
    onSuccess: () => {
      onSave()
    }
  })
  
  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (isEditing) {
      // Only send password if it was changed
      const updateData = { ...formData }
      if (!updateData.password) {
        delete updateData.password
      }
      await updateMutation.mutateAsync({ 
        id: connection.id, 
        data: updateData 
      })
    } else {
      await createMutation.mutateAsync(formData)
    }
  }
  
  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    
    try {
      // Create a temporary connection for testing
      const testData = {
        name: formData.name || 'Test Connection',
        ws_url: formData.ws_url,
        password: formData.password,
        auto_connect: false,
        roles: []
      }
      
      // Create temp connection
      const createResponse = await api.post('/obs', testData)
      const tempId = createResponse.data.id
      
      // Test it
      const testResponse = await api.post(`/obs/${tempId}/test`)
      setTestResult(testResponse.data)
      
      // Delete temp connection
      await api.delete(`/obs/${tempId}`)
      
    } catch (error) {
      setTestResult({
        ok: false,
        error: error.response?.data?.detail || error.message || 'Test failed'
      })
    } finally {
      setTesting(false)
    }
  }
  
  const handleRoleToggle = (role) => {
    setFormData(prev => ({
      ...prev,
      roles: prev.roles.includes(role) 
        ? prev.roles.filter(r => r !== role)
        : [...prev.roles, role]
    }))
  }
  
  const isValid = formData.name && formData.ws_url && formData.password
  
  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Video className="h-5 w-5" />
            {isEditing ? 'Edit OBS Connection' : 'Add OBS Instance'}
          </DialogTitle>
          <DialogDescription>
            Configure connection to an OBS WebSocket server
          </DialogDescription>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name field */}
          <div className="space-y-2">
            <Label htmlFor="name">
              Friendly Name <span className="text-destructive">*</span>
            </Label>
            <Input
              id="name"
              placeholder="e.g., Recording PC, Streaming PC"
              value={formData.name}
              onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
              required
            />
            <p className="text-xs text-muted-foreground">
              A descriptive name to identify this OBS instance
            </p>
          </div>
          
          {/* WebSocket URL field */}
          <div className="space-y-2">
            <Label htmlFor="ws_url">
              WebSocket URL <span className="text-destructive">*</span>
            </Label>
            <Input
              id="ws_url"
              placeholder="ws://host.docker.internal:4455"
              value={formData.ws_url}
              onChange={(e) => setFormData(prev => ({ ...prev, ws_url: e.target.value }))}
              required
            />
            <p className="text-xs text-muted-foreground">
              Use host.docker.internal for host machine, or container name for other containers
            </p>
          </div>
          
          {/* Password field */}
          <div className="space-y-2">
            <Label htmlFor="password">
              Password {isEditing ? '' : <span className="text-destructive">*</span>}
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPassword ? 'text' : 'password'}
                placeholder={isEditing ? 'Leave blank to keep existing' : 'OBS WebSocket password'}
                value={formData.password}
                onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
                required={!isEditing}
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setShowPassword(!showPassword)}
              >
                {showPassword ? (
                  <EyeOff className="h-4 w-4" />
                ) : (
                  <Eye className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Set in OBS → Tools → WebSocket Server Settings
            </p>
          </div>
          
          {/* Auto-connect checkbox */}
          <div className="flex items-center space-x-2">
            <Checkbox
              id="auto_connect"
              checked={formData.auto_connect}
              onCheckedChange={(checked) => 
                setFormData(prev => ({ ...prev, auto_connect: checked }))
              }
            />
            <Label 
              htmlFor="auto_connect" 
              className="text-sm font-normal cursor-pointer"
            >
              Auto-connect on startup
            </Label>
          </div>
          
          {/* Roles checkboxes */}
          <div className="space-y-2">
            <Label>Roles (optional)</Label>
            <div className="space-y-2">
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="role_recording"
                  checked={formData.roles.includes('recording')}
                  onCheckedChange={() => handleRoleToggle('recording')}
                />
                <Label 
                  htmlFor="role_recording" 
                  className="text-sm font-normal cursor-pointer"
                >
                  Recording - This instance is used for recording
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="role_streaming"
                  checked={formData.roles.includes('streaming')}
                  onCheckedChange={() => handleRoleToggle('streaming')}
                />
                <Label 
                  htmlFor="role_streaming" 
                  className="text-sm font-normal cursor-pointer"
                >
                  Streaming - This instance is used for live streaming
                </Label>
              </div>
              <div className="flex items-center space-x-2">
                <Checkbox
                  id="role_backup"
                  checked={formData.roles.includes('backup')}
                  onCheckedChange={() => handleRoleToggle('backup')}
                />
                <Label 
                  htmlFor="role_backup" 
                  className="text-sm font-normal cursor-pointer"
                >
                  Backup - This is a backup recording instance
                </Label>
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Roles help organize multiple OBS instances but don't affect functionality
            </p>
          </div>
          
          {/* Test connection button and result */}
          <div className="space-y-2">
            <Button
              type="button"
              variant="outline"
              onClick={handleTest}
              disabled={!isValid || testing}
              className="w-full"
            >
              {testing ? (
                <>
                  <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                  Testing Connection...
                </>
              ) : (
                <>
                  <TestTube className="h-4 w-4 mr-2" />
                  Test Connection
                </>
              )}
            </Button>
            
            {testResult && (
              <div className={`p-3 rounded-lg ${
                testResult.ok 
                  ? 'bg-success/10 border border-success/20' 
                  : 'bg-destructive/10 border border-destructive/20'
              }`}>
                {testResult.ok ? (
                  <div className="flex items-start gap-2">
                    <Check className="h-4 w-4 text-success mt-0.5" />
                    <div className="flex-1 text-sm">
                      <p className="font-medium text-success">Connection successful!</p>
                      <p className="text-muted-foreground mt-1">
                        {testResult.message || `Connected to OBS ${testResult.obs_version}`}
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-start gap-2">
                    <X className="h-4 w-4 text-destructive mt-0.5" />
                    <div className="flex-1 text-sm">
                      <p className="font-medium text-destructive">Connection failed</p>
                      <p className="text-muted-foreground mt-1">
                        {testResult.error || 'Could not connect to OBS'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </form>
        
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
          <Button 
            onClick={handleSubmit}
            disabled={!isValid || createMutation.isLoading || updateMutation.isLoading}
          >
            {createMutation.isLoading || updateMutation.isLoading ? (
              <>
                <RefreshCw className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              isEditing ? 'Update' : 'Add Connection'
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}