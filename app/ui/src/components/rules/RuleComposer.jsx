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

// Condition field options - must match API's RULE_METADATA fields
const CONDITION_FIELDS = [
  { value: 'file.extension', label: 'File Extension', type: 'select', options: ['.mkv', '.mp4', '.mov', '.avi', '.flv', '.ts'] },
  { value: 'file.size', label: 'File Size', type: 'number' },
  { value: 'file.duration_sec', label: 'Duration (seconds)', type: 'number' },
  { value: 'file.container', label: 'Container Format', type: 'select', options: ['matroska', 'mp4', 'mov', 'avi'] },
  { value: 'file.video_codec', label: 'Video Codec', type: 'select', options: ['h264', 'h265', 'vp9', 'av1'] },
  { value: 'file.audio_codec', label: 'Audio Codec', type: 'select', options: ['aac', 'mp3', 'opus', 'flac'] },
  { value: 'file.width', label: 'Video Width', type: 'number' },
  { value: 'file.height', label: 'Video Height', type: 'number' },
  { value: 'file.fps', label: 'Frame Rate', type: 'number' },
  { value: 'path.abs', label: 'File Path', type: 'path' },
  { value: 'path.glob', label: 'Path Pattern', type: 'text' },
  { value: 'tags.contains', label: 'Has Tag', type: 'text' },
  { value: 'older_than_days', label: 'Age (days)', type: 'number' }
]

// Operator options based on field type - must match API's RULE_METADATA operators
const OPERATORS = {
  text: [
    { value: 'equals', label: 'equals' },
    { value: 'contains', label: 'contains' },
    { value: 'regex', label: 'matches regex' },
    { value: 'matches', label: 'matches pattern' }
  ],
  number: [
    { value: 'equals', label: 'equals' },
    { value: 'gt', label: 'greater than' },
    { value: 'gte', label: 'greater or equal' },
    { value: 'lt', label: 'less than' },
    { value: 'lte', label: 'less or equal' }
  ],
  select: [
    { value: 'equals', label: 'is' },
    { value: 'in', label: 'is one of' }
  ],
  boolean: [
    { value: 'equals', label: 'is' }
  ],
  path: [
    { value: 'equals', label: 'equals' },
    { value: 'contains', label: 'contains' },
    { value: 'matches', label: 'matches pattern' }
  ]
}

// Action types
const ACTION_TYPES = [
  { value: 'ffmpeg_remux', label: 'Remux File', icon: '🔄' },
  { value: 'move', label: 'Move File', icon: '📁' },
  { value: 'copy', label: 'Copy File', icon: '📋' },
  { value: 'proxy', label: 'Create Proxy', icon: '🎬' },
  { value: 'transcode', label: 'Transcode', icon: '🎥' },
  { value: 'tag', label: 'Add Tag', icon: '🏷️' },
  { value: 'webhook', label: 'Call Webhook', icon: '🔗' },
  { value: 'archive', label: 'Archive', icon: '📦' }
]

// Preset templates with conditions and actions
const PRESET_TEMPLATES = {
  'remux_move_proxy': {
    conditions: [
      { field: 'file.extension', operator: 'equals', value: '.mkv' },
      { field: 'file.container', operator: 'equals', value: 'matroska' }
    ],
    actions: [
      { type: 'ffmpeg_remux', parameters: { container: 'mov', faststart: true } },
      { type: 'move', parameters: { target: '' } }, // Will be selected from roles dropdown
      { type: 'proxy', parameters: { codec: 'dnxhr_lb', if_duration_gt: 900 } }
    ]
  },
  'archive_old': {
    conditions: [
      { field: 'older_than_days', operator: 'gt', value: 30 },
      { field: 'path.abs', operator: 'contains', value: '/Recording' }
    ],
    actions: [
      { type: 'move', parameters: { target: '' } } // Will be selected from roles dropdown
    ]
  },
  'transcode_youtube': {
    conditions: [
      { field: 'file.extension', operator: 'in', value: ['.mkv', '.mov', '.mp4'] },
      { field: 'file.width', operator: 'gte', value: 1920 }
    ],
    actions: [
      { type: 'transcode', parameters: { preset: 'youtube_1080p' } },
      { type: 'copy', parameters: { target: '' } } // Will be selected from roles dropdown
    ]
  }
}

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
  
  // Get available drives with roles for target path selection
  const { data: drives } = useQuery({
    queryKey: ['drives', 'status'],
    queryFn: async () => {
      const response = await api.get('/drives/status')
      return response.data
    }
  })
  
  // Initialize rule data
  const [ruleData, setRuleData] = useState(() => {
    if (rule) {
      // Editing existing rule - parse the conditions and actions
      let conditions = []
      let actions = []
      
      // The API returns 'when' field for conditions directly on the rule object
      if (rule.when && Array.isArray(rule.when)) {
        conditions = rule.when.map(c => ({
          field: c.field,
          operator: c.op || c.operator,
          value: c.value
        }))
      }
      
      // The API returns 'do' field for actions directly on the rule object
      if (rule.do && Array.isArray(rule.do)) {
        actions = rule.do.map(action => {
          // Each action in API is like {"ffmpeg_remux": {...params}}
          const actionType = Object.keys(action)[0]
          const parameters = action[actionType] || {}
          return {
            type: actionType,
            parameters: parameters
          }
        })
      }
      
      return {
        name: rule.name,
        description: rule.description || '',
        priority: rule.priority || 100,
        conditions: conditions,
        condition_logic: 'all',
        actions: actions,
        guardrails: rule.guardrails || {},
        schedule: rule.schedule || '',
        quiet_period_sec: rule.quiet_period_sec || 45
      }
    } else if (preset) {
      // Creating from preset - load template conditions and actions
      const template = PRESET_TEMPLATES[preset.id] || { conditions: [], actions: [] }
      return {
        name: preset.label,
        description: preset.description,
        priority: 100,
        conditions: template.conditions || [],
        condition_logic: 'all',
        actions: template.actions || [],
        guardrails: {
          pause_if_recording: true,
          pause_if_gpu_pct_above: 40,
          pause_if_cpu_pct_above: 70
        },
        schedule: '',
        quiet_period_sec: 45
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
        schedule: '',
        quiet_period_sec: 45
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
  
  // Get available target paths from drives with roles
  const getTargetPaths = () => {
    if (!drives || drives.length === 0) return []
    
    const paths = []
    drives.forEach(drive => {
      if (drive.rw && drive.role_details) {
        drive.role_details.forEach(role => {
          // Skip recording role as it's typically for input
          if (role.role !== 'recording') {
            paths.push({
              value: role.path,
              label: `${drive.label} - ${role.role.charAt(0).toUpperCase() + role.role.slice(1)}`,
              role: role.role
            })
          }
        })
      }
    })
    return paths
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
            onValueChange={(value) => updateCondition(index, { value })}
            options={fieldDef.options.map(opt => ({ value: opt, label: opt }))}
            className="w-40"
          />
        )
      }
    } else if (fieldType === 'boolean') {
      return (
        <SimpleSelect
          value={String(condition.value)}
          onValueChange={(value) => updateCondition(index, { value: value === 'true' })}
          options={[
            { value: 'true', label: 'Yes' },
            { value: 'false', label: 'No' }
          ]}
          className="w-32"
        />
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
            value={condition.value || 'none'}
            onValueChange={(value) => updateCondition(index, { value: value === 'none' ? '' : value })}
            options={[
              { value: 'none', label: 'Select path...' },
              ...paths
            ]}
            placeholder="Select path..."
            className="w-48"
          />
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
    const targetPaths = getTargetPaths()
    
    switch (action.type) {
      case 'ffmpeg_remux':
        return (
          <div className="space-y-2 mt-2 p-3 bg-muted/50 rounded-lg">
            <div className="flex items-center space-x-2">
              <label className="text-sm w-24">Container:</label>
              <SimpleSelect
                value={action.parameters.container || 'mov'}
                onValueChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, container: value }
                })}
                options={[
                  { value: 'mov', label: 'MOV' },
                  { value: 'mp4', label: 'MP4' },
                  { value: 'mkv', label: 'MKV' }
                ]}
                className="w-32"
              />
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
                value={action.parameters.target || 'none'}
                onValueChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, target: value === 'none' ? '' : value }
                })}
                options={[
                  { value: 'none', label: 'Select target folder...' },
                  ...targetPaths.map(p => ({
                    value: `${p.value}/{year}/{month}/{filename}`,
                    label: `${p.label}`
                  }))
                ]}
                placeholder="Select target folder..."
                className="flex-1"
              />
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
                onValueChange={(value) => updateAction(index, { 
                  parameters: { ...action.parameters, codec: value }
                })}
                options={[
                  { value: 'dnxhr_lb', label: 'DNxHR LB' },
                  { value: 'dnxhr_sq', label: 'DNxHR SQ' },
                  { value: 'prores_proxy', label: 'ProRes Proxy' },
                  { value: 'h264_proxy', label: 'H.264 Proxy' }
                ]}
                className="w-40"
              />
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
        
      case 'thumbnail':
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
                  onValueChange={(value) => setRuleData(prev => ({ ...prev, condition_logic: value }))}
                  options={[
                    { value: 'all', label: 'All conditions' },
                    { value: 'any', label: 'Any condition' }
                  ]}
                  className="w-32"
                />
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
                    onValueChange={(value) => updateCondition(index, { field: value })}
                    options={CONDITION_FIELDS.map(f => ({ value: f.value, label: f.label }))}
                    className="w-48"
                  />
                  
                  <SimpleSelect
                    value={condition.operator}
                    onValueChange={(value) => updateCondition(index, { operator: value })}
                    options={operators}
                    className="w-32"
                  />
                  
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
                      onValueChange={(value) => updateAction(index, { type: value, parameters: {} })}
                      options={ACTION_TYPES.map(a => ({ value: a.value, label: a.label }))}
                      className="flex-1"
                    />
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
            
            {ruleData.guardrails.pause_if_recording && (
              <div className="flex items-center justify-between ml-6">
                <span className="text-sm text-muted-foreground">Wait time after recording stops</span>
                <div className="flex items-center space-x-2">
                  <Input
                    type="number"
                    value={ruleData.quiet_period_sec || 45}
                    onChange={(e) => setRuleData(prev => ({ 
                      ...prev, 
                      quiet_period_sec: parseInt(e.target.value) || 45
                    }))}
                    className="w-20"
                    min="0"
                    max="3600"
                  />
                  <span className="text-sm">seconds</span>
                </div>
              </div>
            )}
            
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