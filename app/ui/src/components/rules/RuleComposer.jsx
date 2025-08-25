import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  Save,
  X,
  FolderOpen,
  TestTube,
  AlertCircle,
  HelpCircle,
  Settings,
  Shield
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { useApi } from '@/hooks/useApi'
import { SimpleSelect } from '@/components/ui/Select'

// Condition field options
const CONDITION_FIELDS = [
  { value: 'file.extension', label: 'File Extension', type: 'select', options: ['.mkv', '.mp4', '.mov', '.avi', '.flv', '.ts'] },
  { value: 'file.size_mb', label: 'File Size (MB)', type: 'number' },
  { value: 'file.duration_sec', label: 'Duration (seconds)', type: 'number' },
  { value: 'file.age_days', label: 'File Age (days)', type: 'number' },
  { value: 'file.name', label: 'File Name', type: 'text' },
  { value: 'file.path', label: 'File Path', type: 'path' },
  { value: 'event.type', label: 'Event Type', type: 'select', options: ['file.closed', 'file.created', 'asset.indexed'] },
  { value: 'asset.type', label: 'Asset Type', type: 'select', options: ['video', 'audio', 'image'] },
  { value: 'asset.has_proxy', label: 'Has Proxy', type: 'boolean' },
  { value: 'asset.has_thumbnails', label: 'Has Thumbnails', type: 'boolean' }
]

// Operator options based on field type
const OPERATORS = {
  text: [
    { value: '=', label: 'equals' },
    { value: '!=', label: 'not equals' },
    { value: 'contains', label: 'contains' },
    { value: 'starts_with', label: 'starts with' },
    { value: 'ends_with', label: 'ends with' }
  ],
  number: [
    { value: '=', label: 'equals' },
    { value: '!=', label: 'not equals' },
    { value: '>', label: 'greater than' },
    { value: '>=', label: 'greater or equal' },
    { value: '<', label: 'less than' },
    { value: '<=', label: 'less or equal' }
  ],
  select: [
    { value: '=', label: 'is' },
    { value: '!=', label: 'is not' },
    { value: 'in', label: 'is one of' }
  ],
  boolean: [
    { value: '=', label: 'is' }
  ],
  path: [
    { value: '=', label: 'equals' },
    { value: 'contains', label: 'contains' },
    { value: 'starts_with', label: 'starts with' }
  ]
}

// Action types
const ACTION_TYPES = [
  { value: 'ffmpeg_remux', label: 'Remux File', icon: '🔄' },
  { value: 'move', label: 'Move File', icon: '📁' },
  { value: 'copy', label: 'Copy File', icon: '📋' },
  { value: 'proxy', label: 'Create Proxy', icon: '🎬' },
  { value: 'thumbs', label: 'Generate Thumbnails', icon: '🖼️' },
  { value: 'transcode', label: 'Transcode', icon: '🎥' },
  { value: 'tag', label: 'Add Tag', icon: '🏷️' },
  { value: 'webhook', label: 'Call Webhook', icon: '🔗' },
  { value: 'archive', label: 'Archive', icon: '📦' }
]

export default function RuleComposer({ preset, rule, onSave, onCancel, saving }) {
  const { api } = useApi()
  
  // Get available mounts for path selection
  const { data: mounts } = useQuery({
    queryKey: ['system', 'mounts'],
    queryFn: async () => {
      const response = await api.get('/system/mounts')
      return response.data
    }
  })
  
  // Initialize rule data
  const [ruleData, setRuleData] = useState(() => {
    if (rule) {
      // Editing existing rule
      return {
        name: rule.name,
        description: rule.description,
        priority: rule.priority || 100,
        conditions: [], // Parse from rule.rule_json.when
        condition_logic: 'all',
        actions: [], // Parse from rule.rule_json.do
        guardrails: rule.rule_json?.guardrails || {},
        schedule: rule.schedule || ''
      }
    } else if (preset) {
      // Creating from preset
      return {
        name: preset.label,
        description: preset.description,
        priority: 100,
        conditions: [],
        condition_logic: 'all',
        actions: [],
        guardrails: {
          pause_if_recording: true,
          pause_if_gpu_pct_above: 40,
          pause_if_cpu_pct_above: 70
        },
        schedule: ''
      }
    } else {
      // Creating custom
      return {
        name: '',
        description: '',
        priority: 100,
        conditions: [],
        condition_logic: 'all',
        actions: [],
        guardrails: {
          pause_if_recording: true,
          pause_if_gpu_pct_above: 40,
          pause_if_cpu_pct_above: 70
        },
        schedule: ''
      }
    }
  })
  
  // Add a condition
  const addCondition = () => {
    setRuleData(prev => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { field: 'file.extension', operator: '=', value: '.mkv' }
      ]
    }))
  }
  
  // Update a condition
  const updateCondition = (index, updates) => {
    setRuleData(prev => ({
      ...prev,
      conditions: prev.conditions.map((c, i) => 
        i === index ? { ...c, ...updates } : c
      )
    }))
  }
  
  // Remove a condition
  const removeCondition = (index) => {
    setRuleData(prev => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index)
    }))
  }
  
  // Add an action
  const addAction = () => {
    setRuleData(prev => ({
      ...prev,
      actions: [
        ...prev.actions,
        { type: 'ffmpeg_remux', parameters: {} }
      ]
    }))
  }
  
  // Update an action
  const updateAction = (index, updates) => {
    setRuleData(prev => ({
      ...prev,
      actions: prev.actions.map((a, i) => 
        i === index ? { ...a, ...updates } : a
      )
    }))
  }
  
  // Remove an action
  const removeAction = (index) => {
    setRuleData(prev => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index)
    }))
  }
  
  // Get field type
  const getFieldType = (field) => {
    const fieldDef = CONDITION_FIELDS.find(f => f.value === field)
    return fieldDef?.type || 'text'
  }
  
  // Get available paths from mounts
  const getAvailablePaths = () => {
    if (!mounts) return []
    return mounts
      .filter(m => m.rw) // Only writable mounts
      .map(m => ({
        value: m.path,
        label: `${m.label} (${m.path})`
      }))
  }
  
  // Render condition value input based on type
  const renderConditionValue = (condition, index) => {
    const fieldType = getFieldType(condition.field)
    const fieldDef = CONDITION_FIELDS.find(f => f.value === condition.field)
    
    if (fieldType === 'select' && fieldDef?.options) {
      if (condition.operator === 'in') {
        // Multi-select for "in" operator
        return (
          <div className="flex flex-wrap gap-1">
            {fieldDef.options.map(opt => (
              <Badge
                key={opt}
                variant={condition.value?.includes(opt) ? 'default' : 'outline'}
                className="cursor-pointer"
                onClick={() => {
                  const currentValues = condition.value || []
                  const newValues = currentValues.includes(opt)
                    ? currentValues.filter(v => v !== opt)
                    : [...currentValues, opt]
                  updateCondition(index, { value: newValues })
                }}
              >
                {opt}
              </Badge>
            ))}
          </div>
        )
      } else {
        return (
          <SimpleSelect
            value={condition.value}
            onChange={(value) => updateCondition(index, { value })}
            className="w-40"
          >
            {fieldDef.options.map(opt => (
              <option key={opt} value={opt}>{opt}</option>
            ))}
          </SimpleSelect>
        )
      }
    } else if (fieldType === 'boolean') {
      return (
        <SimpleSelect
          value={condition.value}
          onChange={(value) => updateCondition(index, { value: value === 'true' })}
          className="w-32"
        >
          <option value="true">Yes</option>
          <option value="false">No</option>
        </SimpleSelect>
      )
    } else if (fieldType === 'number') {
      return (
        <Input
          type="number"
          value={condition.value}
          onChange={(e) => updateCondition(index, { value: parseFloat(e.target.value) })}
          className="w-32"
        />
      )
    } else if (fieldType === 'path') {
      const paths = getAvailablePaths()
      return (
        <div className="flex items-center space-x-2">
          <SimpleSelect
            value={condition.value}
            onChange={(value) => updateCondition(index, { value })}
            className="w-48"
          >
            <option value="">Select path...</option>
            {paths.map(p => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </SimpleSelect>
        </div>
      )
    } else {
      return (
        <Input
          type="text"
          value={condition.value}
          onChange={(e) => updateCondition(index, { value: e.target.value })}
          className="w-48"
          placeholder="Enter value..."
        />
      )
    }
  }
  
  // Render action parameters based on type
  const renderActionParameters = (action, index) => {
    const paths = getAvailablePaths()
    
    switch (action.type) {
      case 'ffmpeg_remux':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-sm w-24">Container:</label>
              <SimpleSelect
                value={action.parameters.container || 'mov'}
                onChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, container: value }
                })}
                className="w-32"
              >
                <option value="mov">MOV</option>
                <option value="mp4">MP4</option>
                <option value="mkv">MKV</option>
              </SimpleSelect>
            </div>
            <div className="flex items-center space-x-2">
              <label className="text-sm w-24">Fast Start:</label>
              <input
                type="checkbox"
                checked={action.parameters.faststart !== false}
                onChange={(e) => updateAction(index, { 
                  parameters: { ...action.parameters, faststart: e.target.checked }
                })}
              />
            </div>
          </div>
        )
        
      case 'move':
      case 'copy':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-sm w-24">Target:</label>
              <SimpleSelect
                value={action.parameters.target || ''}
                onChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, target: value }
                })}
                className="flex-1"
              >
                <option value="">Select target folder...</option>
                {paths.map(p => (
                  <option key={p.value} value={`${p.value}/{date}/{filename}`}>
                    {p.label} / {'{date}'} / {'{filename}'}
                  </option>
                ))}
              </SimpleSelect>
            </div>
            <p className="text-xs text-muted-foreground">
              Variables: {'{date}'}, {'{year}'}, {'{month}'}, {'{filename}'}
            </p>
          </div>
        )
        
      case 'proxy':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-sm w-32">Codec:</label>
              <SimpleSelect
                value={action.parameters.codec || 'dnxhr_lb'}
                onChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, codec: value }
                })}
                className="w-40"
              >
                <option value="dnxhr_lb">DNxHR LB</option>
                <option value="dnxhr_sq">DNxHR SQ</option>
                <option value="prores_proxy">ProRes Proxy</option>
                <option value="h264_proxy">H.264 Proxy</option>
              </SimpleSelect>
            </div>
            <div className="flex items-center space-x-2">
              <label className="text-sm w-32">Min Duration:</label>
              <Input
                type="number"
                value={action.parameters.if_duration_gt || 0}
                onChange={(e) => updateAction(index, { 
                  parameters: { ...action.parameters, if_duration_gt: parseInt(e.target.value) }
                })}
                className="w-24"
              />
              <span className="text-sm text-muted-foreground">seconds</span>
            </div>
          </div>
        )
        
      case 'thumbs':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-4">
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={action.parameters.poster !== false}
                  onChange={(e) => updateAction(index, { 
                    parameters: { ...action.parameters, poster: e.target.checked }
                  })}
                />
                <span className="text-sm">Poster Frame</span>
              </label>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={action.parameters.sprite !== false}
                  onChange={(e) => updateAction(index, { 
                    parameters: { ...action.parameters, sprite: e.target.checked }
                  })}
                />
                <span className="text-sm">Sprite Sheet</span>
              </label>
              <label className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  checked={action.parameters.hover !== false}
                  onChange={(e) => updateAction(index, { 
                    parameters: { ...action.parameters, hover: e.target.checked }
                  })}
                />
                <span className="text-sm">Hover Preview</span>
              </label>
            </div>
          </div>
        )
        
      case 'tag':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-sm w-24">Tag:</label>
              <Input
                type="text"
                value={action.parameters.tag || ''}
                onChange={(e) => updateAction(index, { 
                  parameters: { ...action.parameters, tag: e.target.value }
                })}
                className="flex-1"
                placeholder="Enter tag name..."
              />
            </div>
          </div>
        )
        
      default:
        return null
    }
  }
  
  const handleSave = () => {
    onSave(ruleData)
  }
  
  const isValid = ruleData.name && 
                  (ruleData.conditions.length > 0 || ruleData.schedule) && 
                  ruleData.actions.length > 0
  
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between">
          {rule ? 'Edit Rule' : preset ? `Create from ${preset.label}` : 'Create Custom Rule'}
          <div className="flex items-center space-x-2">
            <Button variant="outline" onClick={onCancel}>
              <X className="h-4 w-4 mr-2" />
              Cancel
            </Button>
            <Button 
              onClick={handleSave} 
              disabled={!isValid || saving}
            >
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save Rule'}
            </Button>
          </div>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Basic Info */}
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium mb-2 block">Rule Name</label>
            <Input
              value={ruleData.name}
              onChange={(e) => setRuleData(prev => ({ ...prev, name: e.target.value }))}
              placeholder="Enter rule name..."
            />
          </div>
          <div>
            <label className="text-sm font-medium mb-2 block">Description</label>
            <Input
              value={ruleData.description}
              onChange={(e) => setRuleData(prev => ({ ...prev, description: e.target.value }))}
              placeholder="What does this rule do?"
            />
          </div>
        </div>
        
        {/* Conditions */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium">When (Conditions)</h3>
              <p className="text-sm text-muted-foreground">
                Define when this rule should trigger
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={addCondition}>
              <Plus className="h-4 w-4 mr-2" />
              Add Condition
            </Button>
          </div>
          
          {ruleData.conditions.length > 1 && (
            <div className="mb-4 p-3 bg-muted/50 rounded-lg">
              <label className="flex items-center space-x-2">
                <span className="text-sm font-medium">Match:</span>
                <SimpleSelect
                  value={ruleData.condition_logic}
                  onChange={(value) => setRuleData(prev => ({ ...prev, condition_logic: value }))}
                  className="w-32"
                >
                  <option value="all">All conditions</option>
                  <option value="any">Any condition</option>
                </SimpleSelect>
              </label>
            </div>
          )}
          
          <div className="space-y-2">
            {ruleData.conditions.map((condition, index) => {
              const fieldType = getFieldType(condition.field)
              const operators = OPERATORS[fieldType] || OPERATORS.text
              
              return (
                <div key={index} className="flex items-center space-x-2 p-3 bg-muted/30 rounded-lg">
                  <SimpleSelect
                    value={condition.field}
                    onChange={(value) => updateCondition(index, { field: value })}
                    className="w-48"
                  >
                    {CONDITION_FIELDS.map(f => (
                      <option key={f.value} value={f.value}>{f.label}</option>
                    ))}
                  </SimpleSelect>
                  
                  <SimpleSelect
                    value={condition.operator}
                    onChange={(value) => updateCondition(index, { operator: value })}
                    className="w-32"
                  >
                    {operators.map(op => (
                      <option key={op.value} value={op.value}>{op.label}</option>
                    ))}
                  </SimpleSelect>
                  
                  {renderConditionValue(condition, index)}
                  
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => removeCondition(index)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              )
            })}
            
            {ruleData.conditions.length === 0 && (
              <div className="p-4 border-2 border-dashed rounded-lg text-center text-muted-foreground">
                No conditions defined. Click "Add Condition" to start.
              </div>
            )}
          </div>
        </div>
        
        {/* Actions */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium">Do (Actions)</h3>
              <p className="text-sm text-muted-foreground">
                Define what actions to take
              </p>
            </div>
            <Button variant="outline" size="sm" onClick={addAction}>
              <Plus className="h-4 w-4 mr-2" />
              Add Action
            </Button>
          </div>
          
          <div className="space-y-2">
            {ruleData.actions.map((action, index) => {
              const actionDef = ACTION_TYPES.find(a => a.value === action.type)
              
              return (
                <div key={index} className="p-3 bg-muted/30 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <span className="text-2xl">{actionDef?.icon}</span>
                    <SimpleSelect
                      value={action.type}
                      onChange={(value) => updateAction(index, { type: value, parameters: {} })}
                      className="flex-1"
                    >
                      {ACTION_TYPES.map(a => (
                        <option key={a.value} value={a.value}>
                          {a.label}
                        </option>
                      ))}
                    </SimpleSelect>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => removeAction(index)}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                  {renderActionParameters(action, index)}
                </div>
              )
            })}
            
            {ruleData.actions.length === 0 && (
              <div className="p-4 border-2 border-dashed rounded-lg text-center text-muted-foreground">
                No actions defined. Click "Add Action" to start.
              </div>
            )}
          </div>
        </div>
        
        {/* Guardrails */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-medium flex items-center space-x-2">
                <Shield className="h-4 w-4" />
                <span>Guardrails</span>
              </h3>
              <p className="text-sm text-muted-foreground">
                Safety settings to protect your system
              </p>
            </div>
          </div>
          
          <div className="space-y-3 p-4 bg-muted/30 rounded-lg">
            <label className="flex items-center justify-between">
              <span className="text-sm">Pause while recording</span>
              <input
                type="checkbox"
                checked={ruleData.guardrails.pause_if_recording !== false}
                onChange={(e) => setRuleData(prev => ({ 
                  ...prev, 
                  guardrails: { ...prev.guardrails, pause_if_recording: e.target.checked }
                }))}
              />
            </label>
            
            <div className="flex items-center justify-between">
              <span className="text-sm">Pause if GPU above</span>
              <div className="flex items-center space-x-2">
                <Input
                  type="number"
                  value={ruleData.guardrails.pause_if_gpu_pct_above || 40}
                  onChange={(e) => setRuleData(prev => ({ 
                    ...prev, 
                    guardrails: { ...prev.guardrails, pause_if_gpu_pct_above: parseInt(e.target.value) }
                  }))}
                  className="w-20"
                  min="0"
                  max="100"
                />
                <span className="text-sm">%</span>
              </div>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-sm">Pause if CPU above</span>
              <div className="flex items-center space-x-2">
                <Input
                  type="number"
                  value={ruleData.guardrails.pause_if_cpu_pct_above || 70}
                  onChange={(e) => setRuleData(prev => ({ 
                    ...prev, 
                    guardrails: { ...prev.guardrails, pause_if_cpu_pct_above: parseInt(e.target.value) }
                  }))}
                  className="w-20"
                  min="0"
                  max="100"
                />
                <span className="text-sm">%</span>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}