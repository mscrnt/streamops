import { useState } from 'react'
import { 
  Zap, 
  Plus, 
  Edit, 
  Trash2, 
  Play, 
  Pause, 
  Copy, 
  FileText, 
  MoreHorizontal,
  AlertTriangle,
  CheckCircle,
  Clock
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import Input, { Textarea, FormField, Label } from '@/components/ui/Input'
import { SimpleSelect } from '@/components/ui/Select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow, TableSkeleton, TableEmpty } from '@/components/ui/Table'
import { useRules, useCreateRule, useUpdateRule, useDeleteRule } from '@/hooks/useApi'
import { formatRelativeTime } from '@/lib/utils'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@radix-ui/react-dropdown-menu'
import * as Dialog from '@radix-ui/react-dialog'
import toast from 'react-hot-toast'

export default function Rules() {
  // Local state
  const [selectedRules, setSelectedRules] = useState([])
  const [showCreateDialog, setShowCreateDialog] = useState(false)
  const [showEditDialog, setShowEditDialog] = useState(false)
  const [editingRule, setEditingRule] = useState(null)
  const [newRule, setNewRule] = useState({
    name: '',
    description: '',
    enabled: true,
    trigger: 'file_added',
    conditions: '',
    actions: '',
    priority: 100
  })
  
  // API hooks
  const { data: rules, isLoading: rulesLoading } = useRules()
  const createRule = useCreateRule()
  const updateRule = useUpdateRule()
  const deleteRule = useDeleteRule()

  const handleSelectRule = (ruleId) => {
    setSelectedRules(prev => 
      prev.includes(ruleId) 
        ? prev.filter(id => id !== ruleId)
        : [...prev, ruleId]
    )
  }

  const handleSelectAll = () => {
    if (selectedRules.length === rules?.length) {
      setSelectedRules([])
    } else {
      setSelectedRules(rules?.map(rule => rule.id) || [])
    }
  }

  const handleCreateRule = async () => {
    try {
      await createRule.mutateAsync({
        ...newRule,
        conditions: parseYaml(newRule.conditions),
        actions: parseYaml(newRule.actions)
      })
      setShowCreateDialog(false)
      setNewRule({
        name: '',
        description: '',
        enabled: true,
        trigger: 'file_added',
        conditions: '',
        actions: '',
        priority: 100
      })
    } catch (error) {
      toast.error('Failed to create rule')
    }
  }

  const handleEditRule = async () => {
    try {
      await updateRule.mutateAsync({
        ruleId: editingRule.id,
        updates: {
          ...editingRule,
          conditions: parseYaml(editingRule.conditions),
          actions: parseYaml(editingRule.actions)
        }
      })
      setShowEditDialog(false)
      setEditingRule(null)
    } catch (error) {
      toast.error('Failed to update rule')
    }
  }

  const handleToggleRule = async (ruleId, enabled) => {
    try {
      await updateRule.mutateAsync({
        ruleId,
        updates: { enabled }
      })
    } catch (error) {
      toast.error('Failed to toggle rule')
    }
  }

  const parseYaml = (yamlString) => {
    try {
      // Simple YAML parsing - in a real app, use a proper YAML parser
      return yamlString
    } catch (error) {
      throw new Error('Invalid YAML syntax')
    }
  }

  const triggerOptions = [
    { value: 'file_added', label: 'File Added' },
    { value: 'file_modified', label: 'File Modified' },
    { value: 'asset_indexed', label: 'Asset Indexed' },
    { value: 'job_completed', label: 'Job Completed' },
    { value: 'schedule', label: 'Schedule' },
  ]

  const exampleConditions = `# Example conditions (YAML)
when:
  - file_extension: ["mp4", "mov", "avi"]
  - file_size_gt: 100MB
  - path_contains: "recordings"
  - not:
      has_proxy: true`

  const exampleActions = `# Example actions (YAML)
do:
  - ffmpeg_remux:
      output_format: "mov"
      movflags: "+faststart"
  - create_proxy:
      resolution: "1080p"
      codec: "dnxhr_lb"
  - create_thumbnails:
      count: 10
  - tag:
      tags: ["processed", "stream"]`

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Rules</h1>
          <p className="text-muted-foreground">
            Automate workflows with intelligent rules
          </p>
        </div>
        <Button onClick={() => setShowCreateDialog(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Create Rule
        </Button>
      </div>

      {/* Statistics */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Rules</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rules?.length || 0}</div>
            <p className="text-xs text-muted-foreground">
              Configured rules
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Rules</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules?.filter(rule => rule.enabled)?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Currently enabled
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Executions Today</CardTitle>
            <Play className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules?.reduce((sum, rule) => sum + (rule.executions_today || 0), 0) || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Rules triggered
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules?.filter(rule => rule.last_error)?.length || 0}
            </div>
            <p className="text-xs text-muted-foreground">
              Rules with errors
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Rules Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>Automation Rules</CardTitle>
            <div className="flex items-center space-x-2">
              {selectedRules.length > 0 && (
                <>
                  <Button 
                    variant="outline" 
                    size="sm"
                    onClick={() => {
                      selectedRules.forEach(ruleId => {
                        const rule = rules.find(r => r.id === ruleId)
                        if (rule) handleToggleRule(ruleId, !rule.enabled)
                      })
                    }}
                  >
                    Toggle Selected
                  </Button>
                  <Button 
                    variant="destructive" 
                    size="sm"
                    onClick={() => {
                      if (confirm(`Delete ${selectedRules.length} rule(s)?`)) {
                        selectedRules.forEach(ruleId => deleteRule.mutate(ruleId))
                        setSelectedRules([])
                      }
                    }}
                  >
                    Delete Selected
                  </Button>
                </>
              )}
            </div>
          </div>
          <CardDescription>
            Define automated workflows for your media pipeline
          </CardDescription>
        </CardHeader>
        <CardContent>
          {rulesLoading ? (
            <TableSkeleton rows={5} columns={7} />
          ) : !rules || rules.length === 0 ? (
            <TableEmpty
              icon={Zap}
              title="No rules configured"
              description="Create your first automation rule to get started"
              action={
                <Button onClick={() => setShowCreateDialog(true)}>
                  <Plus className="h-4 w-4 mr-2" />
                  Create Rule
                </Button>
              }
            />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-12">
                    <input
                      type="checkbox"
                      checked={selectedRules.length === rules.length}
                      onChange={handleSelectAll}
                      className="rounded border-border"
                    />
                  </TableHead>
                  <TableHead>Rule</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Priority</TableHead>
                  <TableHead>Executions</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead className="w-12"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => {
                  const isSelected = selectedRules.includes(rule.id)
                  
                  return (
                    <TableRow 
                      key={rule.id}
                      className={isSelected ? 'bg-muted/50' : ''}
                    >
                      <TableCell>
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleSelectRule(rule.id)}
                          className="rounded border-border"
                        />
                      </TableCell>
                      
                      <TableCell>
                        <div className="space-y-1">
                          <p className="font-medium">{rule.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {rule.description}
                          </p>
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge variant="outline">
                          {triggerOptions.find(t => t.value === rule.trigger)?.label || rule.trigger}
                        </Badge>
                      </TableCell>
                      
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {rule.enabled ? (
                            <CheckCircle className="h-4 w-4 text-green-500" />
                          ) : (
                            <Pause className="h-4 w-4 text-gray-500" />
                          )}
                          <StatusBadge status={rule.enabled ? 'active' : 'paused'} />
                          {rule.last_error && (
                            <AlertTriangle className="h-4 w-4 text-red-500" title={rule.last_error} />
                          )}
                        </div>
                      </TableCell>
                      
                      <TableCell>
                        <Badge variant="secondary">{rule.priority}</Badge>
                      </TableCell>
                      
                      <TableCell className="text-sm">
                        {rule.execution_count || 0}
                      </TableCell>
                      
                      <TableCell className="text-sm text-muted-foreground">
                        {rule.last_executed_at ? formatRelativeTime(rule.last_executed_at) : 'Never'}
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
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                setEditingRule({...rule, conditions: JSON.stringify(rule.conditions, null, 2), actions: JSON.stringify(rule.actions, null, 2)})
                                setShowEditDialog(true)
                              }}
                            >
                              <Edit className="h-4 w-4 mr-2" />
                              Edit
                            </DropdownMenuItem>
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                setNewRule({
                                  ...rule,
                                  name: `${rule.name} (Copy)`,
                                  conditions: JSON.stringify(rule.conditions, null, 2),
                                  actions: JSON.stringify(rule.actions, null, 2)
                                })
                                setShowCreateDialog(true)
                              }}
                            >
                              <Copy className="h-4 w-4 mr-2" />
                              Duplicate
                            </DropdownMenuItem>
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-accent hover:text-accent-foreground rounded cursor-pointer flex items-center"
                              onClick={() => handleToggleRule(rule.id, !rule.enabled)}
                            >
                              {rule.enabled ? (
                                <>
                                  <Pause className="h-4 w-4 mr-2" />
                                  Disable
                                </>
                              ) : (
                                <>
                                  <Play className="h-4 w-4 mr-2" />
                                  Enable
                                </>
                              )}
                            </DropdownMenuItem>
                            
                            <DropdownMenuSeparator className="h-px bg-border my-1" />
                            
                            <DropdownMenuItem 
                              className="px-2 py-1.5 text-sm hover:bg-destructive hover:text-destructive-foreground rounded cursor-pointer flex items-center"
                              onClick={() => {
                                if (confirm(`Delete rule "${rule.name}"?`)) {
                                  deleteRule.mutate(rule.id)
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

      {/* Create Rule Dialog */}
      <Dialog.Root open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto z-50">
            <Dialog.Title className="text-lg font-semibold mb-4">Create New Rule</Dialog.Title>
            
            <div className="grid gap-6 md:grid-cols-2">
              <div className="space-y-4">
                <FormField label="Rule Name" required>
                  <Input
                    placeholder="Enter rule name"
                    value={newRule.name}
                    onChange={(e) => setNewRule({...newRule, name: e.target.value})}
                  />
                </FormField>
                
                <FormField label="Description">
                  <Textarea
                    placeholder="Describe what this rule does"
                    value={newRule.description}
                    onChange={(e) => setNewRule({...newRule, description: e.target.value})}
                  />
                </FormField>
                
                <FormField label="Trigger">
                  <SimpleSelect
                    options={triggerOptions}
                    value={newRule.trigger}
                    onValueChange={(value) => setNewRule({...newRule, trigger: value})}
                  />
                </FormField>
                
                <FormField label="Priority">
                  <Input
                    type="number"
                    placeholder="100"
                    value={newRule.priority}
                    onChange={(e) => setNewRule({...newRule, priority: parseInt(e.target.value) || 100})}
                  />
                </FormField>
                
                <FormField label="Enabled">
                  <label className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={newRule.enabled}
                      onChange={(e) => setNewRule({...newRule, enabled: e.target.checked})}
                      className="rounded border-border"
                    />
                    <span className="text-sm">Enable this rule</span>
                  </label>
                </FormField>
              </div>
              
              <div className="space-y-4">
                <FormField label="Conditions (YAML)">
                  <Textarea
                    rows={8}
                    placeholder={exampleConditions}
                    value={newRule.conditions}
                    onChange={(e) => setNewRule({...newRule, conditions: e.target.value})}
                    className="font-mono text-sm"
                  />
                </FormField>
                
                <FormField label="Actions (YAML)">
                  <Textarea
                    rows={8}
                    placeholder={exampleActions}
                    value={newRule.actions}
                    onChange={(e) => setNewRule({...newRule, actions: e.target.value})}
                    className="font-mono text-sm"
                  />
                </FormField>
              </div>
            </div>
            
            <div className="flex justify-end space-x-2 mt-6">
              <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleCreateRule}
                loading={createRule.isLoading}
                disabled={!newRule.name.trim()}
              >
                Create Rule
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>

      {/* Edit Rule Dialog */}
      <Dialog.Root open={showEditDialog} onOpenChange={setShowEditDialog}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 bg-black/50 z-50" />
          <Dialog.Content className="fixed top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-background border border-border rounded-lg shadow-lg p-6 w-full max-w-4xl max-h-[90vh] overflow-y-auto z-50">
            <Dialog.Title className="text-lg font-semibold mb-4">Edit Rule</Dialog.Title>
            
            {editingRule && (
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-4">
                  <FormField label="Rule Name" required>
                    <Input
                      value={editingRule.name}
                      onChange={(e) => setEditingRule({...editingRule, name: e.target.value})}
                    />
                  </FormField>
                  
                  <FormField label="Description">
                    <Textarea
                      value={editingRule.description}
                      onChange={(e) => setEditingRule({...editingRule, description: e.target.value})}
                    />
                  </FormField>
                  
                  <FormField label="Trigger">
                    <SimpleSelect
                      options={triggerOptions}
                      value={editingRule.trigger}
                      onValueChange={(value) => setEditingRule({...editingRule, trigger: value})}
                    />
                  </FormField>
                  
                  <FormField label="Priority">
                    <Input
                      type="number"
                      value={editingRule.priority}
                      onChange={(e) => setEditingRule({...editingRule, priority: parseInt(e.target.value) || 100})}
                    />
                  </FormField>
                  
                  <FormField label="Enabled">
                    <label className="flex items-center space-x-2">
                      <input
                        type="checkbox"
                        checked={editingRule.enabled}
                        onChange={(e) => setEditingRule({...editingRule, enabled: e.target.checked})}
                        className="rounded border-border"
                      />
                      <span className="text-sm">Enable this rule</span>
                    </label>
                  </FormField>
                </div>
                
                <div className="space-y-4">
                  <FormField label="Conditions (YAML)">
                    <Textarea
                      rows={8}
                      value={editingRule.conditions}
                      onChange={(e) => setEditingRule({...editingRule, conditions: e.target.value})}
                      className="font-mono text-sm"
                    />
                  </FormField>
                  
                  <FormField label="Actions (YAML)">
                    <Textarea
                      rows={8}
                      value={editingRule.actions}
                      onChange={(e) => setEditingRule({...editingRule, actions: e.target.value})}
                      className="font-mono text-sm"
                    />
                  </FormField>
                </div>
              </div>
            )}
            
            <div className="flex justify-end space-x-2 mt-6">
              <Button variant="outline" onClick={() => setShowEditDialog(false)}>
                Cancel
              </Button>
              <Button 
                onClick={handleEditRule}
                loading={updateRule.isLoading}
                disabled={!editingRule?.name?.trim()}
              >
                Save Changes
              </Button>
            </div>
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
    </div>
  )
}