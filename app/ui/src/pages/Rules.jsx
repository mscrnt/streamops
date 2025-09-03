import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { 
  Zap, 
  Plus, 
  Edit, 
  Trash2, 
  Play, 
  Pause, 
  Copy, 
  MoreHorizontal,
  AlertTriangle,
  CheckCircle,
  Clock,
  Wand2,
  ChevronDown,
  Settings,
  TestTube,
  Save
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge, StatusBadge } from '@/components/ui/Badge'
import Button from '@/components/ui/Button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/Table'
import { useApi } from '@/hooks/useApi'
import { formatRelativeTime } from '@/lib/utils'
import RuleComposer from '@/components/rules/RuleComposer'
import RulePresetCard from '@/components/rules/RulePresetCard'
import toast from 'react-hot-toast'

export default function Rules() {
  const { api } = useApi()
  const queryClient = useQueryClient()
  const [showComposer, setShowComposer] = useState(false)
  const [editingRule, setEditingRule] = useState(null)
  const [showPresets, setShowPresets] = useState(false)
  const [selectedPreset, setSelectedPreset] = useState(null)
  
  // Get rules
  const { data: rulesData, isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: async () => {
      const response = await api.get('/rules/')
      return response.data
    }
  })
  
  // Get rule presets
  const { data: presets } = useQuery({
    queryKey: ['rules', 'presets'],
    queryFn: async () => {
      const response = await api.get('/rules/presets')
      return response.data
    }
  })
  
  // Create rule mutation
  const createMutation = useMutation({
    mutationFn: async (ruleData) => {
      // Transform data to API format
      const apiData = {
        name: ruleData.name,
        enabled: true,
        priority: ruleData.priority || 50,
        trigger: { type: 'file_closed' },
        when: ruleData.conditions.map(c => ({
          field: c.field,
          op: c.operator,
          value: c.value
        })),
        quiet_period_sec: ruleData.quiet_period_sec || 45,
        guardrails: ruleData.guardrails,
        do: ruleData.actions.map(a => ({
          [a.type]: a.parameters || {}
        }))
      }
      
      // First compile the rule
      const compileResponse = await api.post('/rules/compile', apiData)
      if (!compileResponse.data.valid) {
        throw new Error('Invalid rule configuration')
      }
      
      // Then create it - send the rule fields directly
      const response = await api.post('/rules/', compileResponse.data.rule)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['rules'])
      setShowComposer(false)
      setSelectedPreset(null)
      toast.success('Rule created successfully')
    },
    onError: (error) => {
      toast.error(error.message || 'Failed to create rule')
    }
  })
  
  // Update rule mutation
  const updateMutation = useMutation({
    mutationFn: async ({ ruleId, updates }) => {
      const response = await api.put(`/rules/${ruleId}`, updates)
      return response.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['rules'])
      setEditingRule(null)
      setShowComposer(false)
      toast.success('Rule updated successfully')
    }
  })
  
  // Delete rule mutation
  const deleteMutation = useMutation({
    mutationFn: async (ruleId) => {
      await api.delete(`/rules/${ruleId}`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries(['rules'])
      toast.success('Rule deleted successfully')
    }
  })
  
  // Toggle rule enabled/disabled
  const toggleRule = async (rule) => {
    await updateMutation.mutateAsync({
      ruleId: rule.id,
      updates: { enabled: !rule.enabled }
    })
  }
  
  // Create rule from preset
  const handleCreateFromPreset = (preset) => {
    setSelectedPreset(preset)
    setShowComposer(true)
  }
  
  const rules = rulesData?.rules || []
  
  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Automation Rules</h1>
          <p className="text-muted-foreground">
            Create and manage automated workflows for your media files
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <Button
            variant="outline"
            onClick={() => setShowPresets(!showPresets)}
          >
            <Wand2 className="h-4 w-4 mr-2" />
            Use Preset
            <ChevronDown className="h-4 w-4 ml-2" />
          </Button>
          <Button onClick={() => {
            setSelectedPreset(null)
            setShowComposer(true)
          }}>
            <Plus className="h-4 w-4 mr-2" />
            Create Custom Rule
          </Button>
        </div>
      </div>
      
      {/* Preset Cards */}
      {showPresets && presets && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {presets.map(preset => (
            <RulePresetCard
              key={preset.id}
              preset={preset}
              onSelect={handleCreateFromPreset}
            />
          ))}
        </div>
      )}
      
      {/* Rule Composer */}
      {showComposer && (
        <RuleComposer
          preset={selectedPreset}
          rule={editingRule}
          onSave={(ruleData) => {
            if (editingRule) {
              // Update existing rule - use same format as create
              const apiData = {
                name: ruleData.name,
                description: ruleData.description,
                enabled: editingRule.enabled !== false, // Keep existing enabled state
                priority: ruleData.priority || 50,
                trigger: editingRule.trigger || { type: 'file_closed' },
                when: ruleData.conditions.map(c => ({
                  field: c.field,
                  op: c.operator,
                  value: c.value
                })),
                quiet_period_sec: ruleData.quiet_period_sec || 45,
                guardrails: ruleData.guardrails,
                do: ruleData.actions.map(a => ({
                  [a.type]: a.parameters || {}
                }))
              }
              
              updateMutation.mutate({
                ruleId: editingRule.id,
                updates: apiData
              })
            } else {
              // Create new rule
              createMutation.mutate(ruleData)
            }
          }}
          onCancel={() => {
            setShowComposer(false)
            setSelectedPreset(null)
            setEditingRule(null)
          }}
          saving={editingRule ? updateMutation.isPending : createMutation.isPending}
        />
      )}
      
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Rules</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{rules.length}</div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Rules</CardTitle>
            <CheckCircle className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules.filter(r => r.enabled).length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Scheduled</CardTitle>
            <Clock className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules.filter(r => r.schedule).length}
            </div>
          </CardContent>
        </Card>
        
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">With Errors</CardTitle>
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {rules.filter(r => r.last_error).length}
            </div>
          </CardContent>
        </Card>
      </div>
      
      {/* Rules Table */}
      <Card>
        <CardHeader>
          <CardTitle>Configured Rules</CardTitle>
          <CardDescription>
            Manage your automation rules. No coding required!
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
            </div>
          ) : rules.length === 0 ? (
            <div className="text-center py-8">
              <Zap className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <h3 className="text-lg font-medium mb-2">No Rules Yet</h3>
              <p className="text-muted-foreground mb-4">
                Create your first automation rule using presets or the visual composer
              </p>
              <Button onClick={() => setShowPresets(true)}>
                <Wand2 className="h-4 w-4 mr-2" />
                Browse Presets
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Rule</TableHead>
                  <TableHead>Trigger</TableHead>
                  <TableHead>Actions</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Last Run</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map(rule => {
                  const ruleJson = rule.rule_json || {}
                  const conditions = ruleJson.when || {}
                  const actions = ruleJson.do || []
                  
                  return (
                    <TableRow key={rule.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{rule.name}</p>
                          {rule.description && (
                            <p className="text-sm text-muted-foreground">
                              {rule.description}
                            </p>
                          )}
                          {rule.priority !== 100 && (
                            <Badge variant="outline" className="mt-1">
                              Priority: {rule.priority}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="space-y-1">
                          {rule.schedule ? (
                            <Badge variant="secondary">
                              <Clock className="h-3 w-3 mr-1" />
                              Scheduled
                            </Badge>
                          ) : (
                            <Badge variant="secondary">
                              Event-based
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {actions.slice(0, 3).map((action, idx) => (
                            <Badge key={idx} variant="outline">
                              {action.action}
                            </Badge>
                          ))}
                          {actions.length > 3 && (
                            <Badge variant="outline">
                              +{actions.length - 3} more
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center space-x-2">
                          {rule.enabled ? (
                            <Badge variant="success">
                              <Play className="h-3 w-3 mr-1" />
                              Active
                            </Badge>
                          ) : (
                            <Badge variant="secondary">
                              <Pause className="h-3 w-3 mr-1" />
                              Paused
                            </Badge>
                          )}
                          {rule.last_error && (
                            <Badge variant="destructive">
                              Error
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        {rule.last_run ? (
                          <span className="text-sm text-muted-foreground">
                            {formatRelativeTime(rule.last_run)}
                          </span>
                        ) : (
                          <span className="text-sm text-muted-foreground">
                            Never
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end space-x-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => toggleRule(rule)}
                          >
                            {rule.enabled ? (
                              <Pause className="h-4 w-4" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditingRule(rule)
                              setShowComposer(true)
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              if (confirm(`Delete rule "${rule.name}"?`)) {
                                deleteMutation.mutate(rule.id)
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}