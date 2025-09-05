import React, { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { 
  Plus, Trash2, Edit2, Save, X, CheckCircle, XCircle, 
  Loader2, Eye, EyeOff, TestTube, Info, Video, Wifi, WifiOff,
  Settings, Power, PowerOff
} from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import { Badge } from '@/components/ui/Badge';
import Checkbox from '@/components/ui/Checkbox';
import { cn } from '@/lib/utils';
import * as Dialog from '@radix-ui/react-dialog';

const OBSSettings = () => {
  const { api } = useApi();
  const queryClient = useQueryClient();
  const [connections, setConnections] = useState([]);
  const [editingConnection, setEditingConnection] = useState(null);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [showPasswordFor, setShowPasswordFor] = useState({});
  const [testingConnection, setTestingConnection] = useState(null);
  
  // New connection form
  const [newConnection, setNewConnection] = useState({
    name: '',
    ws_url: 'ws://host.docker.internal:4455',
    password: '',
    auto_connect: true,
    roles: []
  });

  // Fetch OBS connections
  const { data: obsData, isLoading, refetch } = useQuery({
    queryKey: ['obs', 'connections'],
    queryFn: () => api.get('/obs').then(r => r.data)
  });

  // Update state when data loads
  useEffect(() => {
    if (obsData) {
      // Handle both array response and object with connections property
      setConnections(Array.isArray(obsData) ? obsData : obsData.connections || []);
    }
  }, [obsData]);

  // Create connection mutation
  const createMutation = useMutation({
    mutationFn: (data) => api.post('/obs', data),
    onSuccess: () => {
      queryClient.invalidateQueries(['obs']);
      toast.success('OBS connection added');
      setShowAddDialog(false);
      setNewConnection({
        name: '',
        ws_url: 'ws://host.docker.internal:4455',
        password: '',
        auto_connect: true,
        roles: []
      });
      refetch();
    },
    onError: (error) => {
      toast.error(`Failed to add: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Update connection mutation
  const updateMutation = useMutation({
    mutationFn: ({ id, ...data }) => api.put(`/obs/${id}`, data),
    onSuccess: () => {
      queryClient.invalidateQueries(['obs']);
      toast.success('Connection updated');
      setEditingConnection(null);
      refetch();
    },
    onError: (error) => {
      toast.error(`Failed to update: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Delete connection mutation
  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/obs/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries(['obs']);
      toast.success('Connection removed');
      refetch();
    },
    onError: (error) => {
      toast.error(`Failed to delete: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Test connection mutation
  const testMutation = useMutation({
    mutationFn: (id) => api.post(`/obs/${id}/test`),
    onSuccess: (response, id) => {
      setTestingConnection(null);
      if (response.data.ok) {
        toast.success(`Connected to OBS ${response.data.obs_version || ''}`);
      } else {
        toast.error(response.data.error || 'Connection failed');
      }
    },
    onError: (error) => {
      setTestingConnection(null);
      toast.error(`Test failed: ${error.response?.data?.detail || error.message}`);
    }
  });

  // Connect/disconnect mutation
  const toggleConnectionMutation = useMutation({
    mutationFn: ({ id, connect }) => 
      connect ? api.post(`/obs/${id}/connect`) : api.post(`/obs/${id}/disconnect`),
    onSuccess: (_, { connect }) => {
      queryClient.invalidateQueries(['obs']);
      toast.success(connect ? 'Connected' : 'Disconnected');
      refetch();
    },
    onError: (error) => {
      toast.error(`Failed: ${error.response?.data?.detail || error.message}`);
    }
  });

  const handleAddConnection = () => {
    if (!newConnection.name || !newConnection.ws_url) {
      toast.error('Name and URL are required');
      return;
    }
    createMutation.mutate(newConnection);
  };

  const handleUpdateConnection = (connection) => {
    updateMutation.mutate(connection);
  };

  const handleDeleteConnection = (id, name) => {
    if (window.confirm(`Delete OBS connection "${name}"?`)) {
      deleteMutation.mutate(id);
    }
  };

  const handleTestConnection = (id) => {
    setTestingConnection(id);
    testMutation.mutate(id);
  };

  const handleToggleConnection = (id, currentlyConnected) => {
    toggleConnectionMutation.mutate({ id, connect: !currentlyConnected });
  };

  const toggleRole = (roles, role) => {
    if (!roles) return [role];
    if (roles.includes(role)) {
      return roles.filter(r => r !== role);
    }
    return [...roles, role];
  };

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold mb-1">OBS Integration</h1>
        <p className="text-muted-foreground">
          Manage multiple OBS WebSocket connections for recording detection and automation
        </p>
      </div>

      {/* Connections List */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>OBS Connections</CardTitle>
              <CardDescription>
                {connections.length} connection{connections.length !== 1 ? 's' : ''} configured
              </CardDescription>
            </div>
            <Button onClick={() => setShowAddDialog(true)}>
              <Plus className="h-4 w-4 mr-2" />
              Add Connection
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {connections.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              <Video className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p>No OBS connections configured</p>
              <p className="text-sm mt-1">Add a connection to enable recording detection</p>
            </div>
          ) : (
            <div className="space-y-4">
              {connections.map((connection) => (
                <div key={connection.id} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <h3 className="font-medium">{connection.name}</h3>
                        {connection.connected ? (
                          <Badge variant="success" className="text-xs">
                            <Wifi className="h-3 w-3 mr-1" />
                            Connected
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-xs">
                            <WifiOff className="h-3 w-3 mr-1" />
                            Disconnected
                          </Badge>
                        )}
                        {connection.recording && (
                          <Badge variant="destructive" className="text-xs">
                            Recording
                          </Badge>
                        )}
                        {connection.streaming && (
                          <Badge variant="warning" className="text-xs">
                            Streaming
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{connection.ws_url}</p>
                    </div>
                    
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTestConnection(connection.id)}
                        disabled={testingConnection === connection.id}
                        title="Test Connection"
                      >
                        {testingConnection === connection.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <TestTube className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleToggleConnection(connection.id, connection.connected)}
                        title={connection.connected ? "Disconnect from OBS" : "Connect to OBS"}
                      >
                        {connection.connected ? (
                          <PowerOff className="h-4 w-4" />
                        ) : (
                          <Power className="h-4 w-4" />
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditingConnection(connection)}
                        title="Edit Connection Settings"
                      >
                        <Edit2 className="h-4 w-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteConnection(connection.id, connection.name)}
                        className="text-destructive hover:text-destructive"
                        title="Delete Connection"
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                  
                  {/* Connection Details */}
                  <div className="text-sm space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Auto-connect:</span>
                      <span>{connection.auto_connect ? 'Yes' : 'No'}</span>
                    </div>
                    {connection.roles && connection.roles.length > 0 && (
                      <div className="flex items-center justify-between">
                        <span className="text-muted-foreground">Roles:</span>
                        <div className="flex gap-1">
                          {connection.roles.map(role => (
                            <Badge key={role} variant="secondary" className="text-xs">
                              {role}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {connection.last_error && (
                      <div className="mt-2 p-2 bg-destructive/10 rounded text-xs text-destructive">
                        {connection.last_error}
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add Connection Dialog */}
      <Dialog.Root open={showAddDialog} onOpenChange={setShowAddDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50" />
          <Dialog.Content className="fixed left-[50%] top-[50%] max-h-[85vh] w-[90vw] max-w-[450px] translate-x-[-50%] translate-y-[-50%] rounded-lg bg-background p-6 shadow-lg z-50">
            <Dialog.Title className="text-lg font-semibold mb-4">
              Add OBS Connection
            </Dialog.Title>
            
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1 block">Name</label>
                <Input
                  value={newConnection.name}
                  onChange={(e) => setNewConnection({...newConnection, name: e.target.value})}
                  placeholder="e.g., Main PC, Gaming Rig"
                />
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">WebSocket URL</label>
                <Input
                  value={newConnection.ws_url}
                  onChange={(e) => setNewConnection({...newConnection, ws_url: e.target.value})}
                  placeholder="ws://localhost:4455"
                />
              </div>
              
              <div>
                <label className="text-sm font-medium mb-1 block">Password (optional)</label>
                <Input
                  type="password"
                  value={newConnection.password}
                  onChange={(e) => setNewConnection({...newConnection, password: e.target.value})}
                  placeholder="OBS WebSocket password"
                />
              </div>
              
              <div className="flex items-center gap-2">
                <Checkbox
                  id="new-auto-connect"
                  checked={newConnection.auto_connect}
                  onCheckedChange={(checked) => setNewConnection({...newConnection, auto_connect: checked})}
                />
                <label htmlFor="new-auto-connect" className="text-sm font-medium cursor-pointer">
                  Auto-connect on startup
                </label>
              </div>
              
              <div>
                <label className="text-sm font-medium mb-2 block">Roles (optional)</label>
                <div className="flex gap-2">
                  <Button
                    variant={newConnection.roles?.includes('recording') ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setNewConnection({
                      ...newConnection,
                      roles: toggleRole(newConnection.roles, 'recording')
                    })}
                  >
                    Recording
                  </Button>
                  <Button
                    variant={newConnection.roles?.includes('streaming') ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setNewConnection({
                      ...newConnection,
                      roles: toggleRole(newConnection.roles, 'streaming')
                    })}
                  >
                    Streaming
                  </Button>
                </div>
              </div>
            </div>
            
            <div className="flex justify-end gap-2 mt-6">
              <Button variant="outline" onClick={() => setShowAddDialog(false)}>
                Cancel
              </Button>
              <Button onClick={handleAddConnection}>
                Add Connection
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Edit Connection Dialog */}
      {editingConnection && (
        <Dialog.Root open={!!editingConnection} onOpenChange={() => setEditingConnection(null)}>
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-background/80 backdrop-blur-sm z-50" />
            <Dialog.Content className="fixed left-[50%] top-[50%] max-h-[85vh] w-[90vw] max-w-[450px] translate-x-[-50%] translate-y-[-50%] rounded-lg bg-background p-6 shadow-lg z-50">
              <Dialog.Title className="text-lg font-semibold mb-4">
                Edit OBS Connection
              </Dialog.Title>
              
              <div className="space-y-4">
                <div>
                  <label className="text-sm font-medium mb-1 block">Name</label>
                  <Input
                    value={editingConnection.name}
                    onChange={(e) => setEditingConnection({...editingConnection, name: e.target.value})}
                    placeholder="Connection name"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1 block">WebSocket URL</label>
                  <Input
                    value={editingConnection.ws_url}
                    onChange={(e) => setEditingConnection({...editingConnection, ws_url: e.target.value})}
                    placeholder="ws://localhost:4455"
                  />
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-1 block">Password</label>
                  <Input
                    type="password"
                    value={editingConnection.password || ''}
                    onChange={(e) => setEditingConnection({...editingConnection, password: e.target.value})}
                    placeholder="Leave blank to keep current"
                  />
                </div>
                
                <div className="flex items-center gap-2">
                  <Checkbox
                    id="edit-auto-connect"
                    checked={editingConnection.auto_connect}
                    onCheckedChange={(checked) => setEditingConnection({...editingConnection, auto_connect: checked})}
                  />
                  <label htmlFor="edit-auto-connect" className="text-sm font-medium cursor-pointer">
                    Auto-connect on startup
                  </label>
                </div>
                
                <div>
                  <label className="text-sm font-medium mb-2 block">Roles</label>
                  <div className="flex gap-2">
                    <Button
                      variant={editingConnection.roles?.includes('recording') ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setEditingConnection({
                        ...editingConnection,
                        roles: toggleRole(editingConnection.roles, 'recording')
                      })}
                    >
                      Recording
                    </Button>
                    <Button
                      variant={editingConnection.roles?.includes('streaming') ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setEditingConnection({
                        ...editingConnection,
                        roles: toggleRole(editingConnection.roles, 'streaming')
                      })}
                    >
                      Streaming
                    </Button>
                  </div>
                </div>
              </div>
              
              <div className="flex justify-end gap-2 mt-6">
                <Button variant="outline" onClick={() => setEditingConnection(null)}>
                  Cancel
                </Button>
                <Button onClick={() => handleUpdateConnection(editingConnection)}>
                  Save Changes
                </Button>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        </Dialog.Root>
      )}
    </div>
  );
};

export default OBSSettings;