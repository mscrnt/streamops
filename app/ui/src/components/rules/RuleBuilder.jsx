import { useState, useEffect } from 'react'
import { 
  X, Save, Play, Code, HelpCircle, Plus, Trash2, 
  ChevronDown, Clock, Calendar, AlertCircle, CheckCircle,
  FileText, Wand2
} from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'
import toast from 'react-hot-toast'

export default function RuleBuilder({ 
  rule, 
  metadata, 
  onSave, 
  onTest, 
  onCompile,
  onClose,
  testResults 
}) {
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    enabled: true,
    priority: 50,
    quiet_period_sec: 45,
    active_hours: {
      enabled: false,
      start: '00:00',
      end: '23:59',
      days: [1, 2, 3, 4, 5, 6, 7]
    },
    conditions: [],
    actions: [],
    guardrails: [],
    rule_yaml: ''
  })
  
  const [mode, setMode] = useState('guided') // 'guided' or 'yaml'
  const [errors, setErrors] = useState({})
  
  useEffect(() => {
    if (rule) {
      setFormData({
        ...rule,
        conditions: rule.conditions || [],
        actions: rule.actions || [],
        guardrails: rule.guardrails || []
      })
      if (rule.rule_yaml) {
        setMode('yaml')
      }
    }
  }, [rule])
  
  const handleChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    // Clear error for this field
    setErrors(prev => ({ ...prev, [field]: null }))
  }
  
  const handleActiveHoursChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      active_hours: {
        ...prev.active_hours,
        [field]: value
      }
    }))
  }
  
  const toggleDay = (day) => {
    setFormData(prev => {
      const days = prev.active_hours.days || []
      const newDays = days.includes(day) 
        ? days.filter(d => d !== day)
        : [...days, day].sort()
      
      return {
        ...prev,
        active_hours: {
          ...prev.active_hours,
          days: newDays
        }
      }
    })
  }
  
  const addCondition = () => {
    setFormData(prev => ({
      ...prev,
      conditions: [
        ...prev.conditions,
        { type: 'filename_pattern', params: { pattern: '' } }
      ]
    }))
  }
  
  const updateCondition = (index, field, value) => {
    setFormData(prev => {
      const conditions = [...prev.conditions]
      if (field === 'type') {
        // Reset params when type changes
        conditions[index] = {
          type: value,
          params: getDefaultParams('condition', value)
        }
      } else {
        conditions[index] = {
          ...conditions[index],
          [field]: value
        }
      }
      return { ...prev, conditions }
    })
  }
  
  const removeCondition = (index) => {
    setFormData(prev => ({
      ...prev,
      conditions: prev.conditions.filter((_, i) => i !== index)
    }))
  }
  
  const addAction = () => {
    setFormData(prev => ({
      ...prev,
      actions: [
        ...prev.actions,
        { type: 'ffmpeg_remux', params: {} }
      ]
    }))
  }
  
  const updateAction = (index, field, value) => {
    setFormData(prev => {
      const actions = [...prev.actions]
      if (field === 'type') {
        actions[index] = {
          type: value,
          params: getDefaultParams('action', value)
        }
      } else {
        actions[index] = {
          ...actions[index],
          [field]: value
        }
      }
      return { ...prev, actions }
    })
  }
  
  const removeAction = (index) => {
    setFormData(prev => ({
      ...prev,
      actions: prev.actions.filter((_, i) => i !== index)
    }))
  }
  
  const addGuardrail = () => {
    setFormData(prev => ({
      ...prev,
      guardrails: [
        ...prev.guardrails,
        { type: 'pause_if_recording', params: {} }
      ]
    }))
  }
  
  const updateGuardrail = (index, field, value) => {
    setFormData(prev => {
      const guardrails = [...prev.guardrails]
      if (field === 'type') {
        guardrails[index] = {
          type: value,
          params: getDefaultParams('guardrail', value)
        }
      } else {
        guardrails[index] = {
          ...guardrails[index],
          [field]: value
        }
      }
      return { ...prev, guardrails }
    })
  }
  
  const removeGuardrail = (index) => {
    setFormData(prev => ({
      ...prev,
      guardrails: prev.guardrails.filter((_, i) => i !== index)
    }))
  }
  
  const getDefaultParams = (category, type) => {
    if (!metadata) return {}
    
    const items = category === 'condition' ? metadata.conditions :
                  category === 'action' ? metadata.actions :
                  metadata.guardrails
    
    const item = items?.find(i => i.name === type)
    if (!item?.params) return {}
    
    const params = {}
    Object.entries(item.params).forEach(([key, schema]) => {
      if (schema.default !== undefined) {
        params[key] = schema.default
      } else if (schema.type === 'string') {
        params[key] = ''
      } else if (schema.type === 'number') {
        params[key] = 0
      } else if (schema.type === 'boolean') {
        params[key] = false
      } else if (schema.type === 'array') {
        params[key] = []
      }
    })
    
    return params
  }
  
  const buildYamlFromGuided = () => {
    const yaml = []
    
    yaml.push(`name: "${formData.name}"`)
    if (formData.description) {
      yaml.push(`description: "${formData.description}"`)
    }
    yaml.push(`enabled: ${formData.enabled}`)
    yaml.push(`priority: ${formData.priority}`)
    yaml.push(`quiet_period_sec: ${formData.quiet_period_sec}`)
    
    if (formData.active_hours?.enabled) {
      yaml.push('active_hours:')
      yaml.push(`  enabled: true`)
      yaml.push(`  start: "${formData.active_hours.start}"`)
      yaml.push(`  end: "${formData.active_hours.end}"`)
      yaml.push(`  days: [${formData.active_hours.days.join(', ')}]`)
    }
    
    if (formData.conditions.length > 0) {
      yaml.push('')
      yaml.push('when:')
      formData.conditions.forEach(cond => {
        yaml.push(`  - ${cond.type}:`)
        Object.entries(cond.params || {}).forEach(([key, value]) => {
          if (typeof value === 'string') {
            yaml.push(`      ${key}: "${value}"`)
          } else if (Array.isArray(value)) {
            yaml.push(`      ${key}: [${value.map(v => `"${v}"`).join(', ')}]`)
          } else {
            yaml.push(`      ${key}: ${value}`)
          }
        })
      })
    }
    
    if (formData.actions.length > 0) {
      yaml.push('')
      yaml.push('do:')
      formData.actions.forEach(action => {
        yaml.push(`  - ${action.type}:`)
        Object.entries(action.params || {}).forEach(([key, value]) => {
          if (typeof value === 'string') {
            yaml.push(`      ${key}: "${value}"`)
          } else if (Array.isArray(value)) {
            yaml.push(`      ${key}: [${value.map(v => `"${v}"`).join(', ')}]`)
          } else {
            yaml.push(`      ${key}: ${value}`)
          }
        })
      })
    }
    
    if (formData.guardrails.length > 0) {
      yaml.push('')
      yaml.push('guardrails:')
      formData.guardrails.forEach(guard => {
        yaml.push(`  - ${guard.type}:`)
        Object.entries(guard.params || {}).forEach(([key, value]) => {
          if (typeof value === 'string') {
            yaml.push(`      ${key}: "${value}"`)
          } else {
            yaml.push(`      ${key}: ${value}`)
          }
        })
      })
    }
    
    return yaml.join('\n')
  }
  
  const handleSave = async () => {
    // Validate
    const newErrors = {}
    if (!formData.name) newErrors.name = 'Name is required'
    if (mode === 'guided' && formData.actions.length === 0) {
      newErrors.actions = 'At least one action is required'
    }
    if (mode === 'yaml' && !formData.rule_yaml) {
      newErrors.rule_yaml = 'YAML content is required'
    }
    
    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      toast.error('Please fix validation errors')
      return
    }
    
    // Build final data
    const data = { ...formData }
    if (mode === 'guided') {
      data.rule_yaml = buildYamlFromGuided()
    }
    
    await onSave(data)
  }
  
  const handleTest = async () => {
    const data = { ...formData }
    if (mode === 'guided') {
      data.rule_yaml = buildYamlFromGuided()
    }
    await onTest(data)
  }
  
  const handleCompile = async () => {
    const data = { ...formData }
    if (mode === 'guided') {
      data.rule_yaml = buildYamlFromGuided()
    }
    const result = await onCompile(data)
    if (result) {
      toast.success('View compiled output in console')
      console.log('Compiled rule:', result)
    }
  }
  
  const dayLabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  
  return (
    <>
      {/* Backdrop */}
      <div 
        className="fixed inset-0 bg-black/50 z-40"
        onClick={onClose}
      />
      
      {/* Modal */}
      <div className="fixed inset-4 bg-background border border-border rounded-lg z-50 flex flex-col max-w-4xl mx-auto my-8">
        {/* Header */}
        <div className="p-6 border-b border-border">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold">
                {rule ? 'Edit Rule' : 'Create Rule'}
              </h2>
              <p className="text-sm text-muted-foreground mt-1">
                Configure automation rule conditions and actions
              </p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={onClose}
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
          
          {/* Mode Toggle */}
          <div className="flex gap-2 mt-4">
            <Button
              size="sm"
              variant={mode === 'guided' ? 'default' : 'outline'}
              onClick={() => setMode('guided')}
            >
              <Wand2 className="w-4 h-4 mr-2" />
              Guided Builder
            </Button>
            <Button
              size="sm"
              variant={mode === 'yaml' ? 'default' : 'outline'}
              onClick={() => setMode('yaml')}
            >
              <Code className="w-4 h-4 mr-2" />
              YAML Editor
            </Button>
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {mode === 'guided' ? (
            <div className="space-y-6">
              {/* Basic Info */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Basic Information</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Rule Name *
                    </label>
                    <input
                      type="text"
                      className={cn(
                        "w-full px-3 py-2 border rounded-lg",
                        errors.name && "border-destructive"
                      )}
                      value={formData.name}
                      onChange={e => handleChange('name', e.target.value)}
                      placeholder="e.g., Auto-remux recordings"
                    />
                    {errors.name && (
                      <p className="text-xs text-destructive mt-1">{errors.name}</p>
                    )}
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Description
                    </label>
                    <textarea
                      className="w-full px-3 py-2 border rounded-lg resize-none"
                      rows={2}
                      value={formData.description}
                      onChange={e => handleChange('description', e.target.value)}
                      placeholder="Optional description of what this rule does"
                    />
                  </div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Priority
                      </label>
                      <input
                        type="number"
                        className="w-full px-3 py-2 border rounded-lg"
                        value={formData.priority}
                        onChange={e => handleChange('priority', parseInt(e.target.value))}
                        min={1}
                        max={100}
                      />
                    </div>
                    
                    <div>
                      <label className="block text-sm font-medium mb-2">
                        Status
                      </label>
                      <select
                        className="w-full px-3 py-2 border rounded-lg"
                        value={formData.enabled}
                        onChange={e => handleChange('enabled', e.target.value === 'true')}
                      >
                        <option value="true">Enabled</option>
                        <option value="false">Disabled</option>
                      </select>
                    </div>
                  </div>
                </CardContent>
              </Card>
              
              {/* Quiet Period */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Clock className="w-4 h-4" />
                    Quiet Period
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div>
                    <label className="block text-sm font-medium mb-2">
                      Wait time after file creation (seconds)
                    </label>
                    <input
                      type="number"
                      className="w-full px-3 py-2 border rounded-lg"
                      value={formData.quiet_period_sec}
                      onChange={e => handleChange('quiet_period_sec', parseInt(e.target.value))}
                      min={0}
                      placeholder="45"
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Prevents processing files that are still being written
                    </p>
                  </div>
                </CardContent>
              </Card>
              
              {/* Active Hours */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    Active Hours
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="active-hours-enabled"
                      checked={formData.active_hours?.enabled}
                      onChange={e => handleActiveHoursChange('enabled', e.target.checked)}
                    />
                    <label htmlFor="active-hours-enabled" className="text-sm">
                      Restrict rule to specific hours
                    </label>
                  </div>
                  
                  {formData.active_hours?.enabled && (
                    <>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium mb-2">
                            Start Time
                          </label>
                          <input
                            type="time"
                            className="w-full px-3 py-2 border rounded-lg"
                            value={formData.active_hours.start}
                            onChange={e => handleActiveHoursChange('start', e.target.value)}
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium mb-2">
                            End Time
                          </label>
                          <input
                            type="time"
                            className="w-full px-3 py-2 border rounded-lg"
                            value={formData.active_hours.end}
                            onChange={e => handleActiveHoursChange('end', e.target.value)}
                          />
                        </div>
                      </div>
                      
                      <div>
                        <label className="block text-sm font-medium mb-2">
                          Active Days
                        </label>
                        <div className="flex gap-2">
                          {dayLabels.map((day, index) => (
                            <button
                              key={index}
                              className={cn(
                                "px-3 py-1 text-xs rounded-lg border transition-colors",
                                formData.active_hours.days?.includes(index + 1)
                                  ? "bg-primary text-primary-foreground border-primary"
                                  : "border-border hover:border-primary"
                              )}
                              onClick={() => toggleDay(index + 1)}
                            >
                              {day}
                            </button>
                          ))}
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
              
              {/* Conditions */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Conditions (When)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {formData.conditions.map((condition, index) => (
                    <div key={index} className="p-3 border rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <select
                          className="flex-1 px-3 py-2 border rounded-lg mr-2"
                          value={condition.type}
                          onChange={e => updateCondition(index, 'type', e.target.value)}
                        >
                          {metadata?.conditions?.map(c => (
                            <option key={c.name} value={c.name}>
                              {c.display_name}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => removeCondition(index)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      
                      {/* Dynamic params based on condition type */}
                      {metadata?.conditions?.find(c => c.name === condition.type)?.params && (
                        <div className="space-y-2 pl-4">
                          {Object.entries(
                            metadata.conditions.find(c => c.name === condition.type).params
                          ).map(([key, schema]) => (
                            <div key={key}>
                              <label className="block text-xs font-medium mb-1">
                                {schema.display_name || key}
                              </label>
                              {schema.type === 'string' && schema.enum ? (
                                <select
                                  className="w-full px-2 py-1 text-sm border rounded"
                                  value={condition.params[key] || ''}
                                  onChange={e => updateCondition(index, 'params', {
                                    ...condition.params,
                                    [key]: e.target.value
                                  })}
                                >
                                  <option value="">Select...</option>
                                  {schema.enum.map(opt => (
                                    <option key={opt} value={opt}>{opt}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={schema.type === 'number' ? 'number' : 'text'}
                                  className="w-full px-2 py-1 text-sm border rounded"
                                  value={condition.params[key] || ''}
                                  onChange={e => updateCondition(index, 'params', {
                                    ...condition.params,
                                    [key]: schema.type === 'number' 
                                      ? parseFloat(e.target.value) 
                                      : e.target.value
                                  })}
                                  placeholder={schema.placeholder}
                                />
                              )}
                              {schema.description && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  {schema.description}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={addCondition}
                    className="w-full"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Condition
                  </Button>
                </CardContent>
              </Card>
              
              {/* Actions */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Actions (Do)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {formData.actions.map((action, index) => (
                    <div key={index} className="p-3 border rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <select
                          className="flex-1 px-3 py-2 border rounded-lg mr-2"
                          value={action.type}
                          onChange={e => updateAction(index, 'type', e.target.value)}
                        >
                          {metadata?.actions?.map(a => (
                            <option key={a.name} value={a.name}>
                              {a.display_name}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => removeAction(index)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      
                      {/* Dynamic params based on action type */}
                      {metadata?.actions?.find(a => a.name === action.type)?.params && (
                        <div className="space-y-2 pl-4">
                          {Object.entries(
                            metadata.actions.find(a => a.name === action.type).params
                          ).map(([key, schema]) => (
                            <div key={key}>
                              <label className="block text-xs font-medium mb-1">
                                {schema.display_name || key}
                              </label>
                              {schema.type === 'boolean' ? (
                                <input
                                  type="checkbox"
                                  checked={action.params[key] || false}
                                  onChange={e => updateAction(index, 'params', {
                                    ...action.params,
                                    [key]: e.target.checked
                                  })}
                                />
                              ) : schema.enum ? (
                                <select
                                  className="w-full px-2 py-1 text-sm border rounded"
                                  value={action.params[key] || ''}
                                  onChange={e => updateAction(index, 'params', {
                                    ...action.params,
                                    [key]: e.target.value
                                  })}
                                >
                                  <option value="">Select...</option>
                                  {schema.enum.map(opt => (
                                    <option key={opt} value={opt}>{opt}</option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={schema.type === 'number' ? 'number' : 'text'}
                                  className="w-full px-2 py-1 text-sm border rounded"
                                  value={action.params[key] || ''}
                                  onChange={e => updateAction(index, 'params', {
                                    ...action.params,
                                    [key]: schema.type === 'number' 
                                      ? parseFloat(e.target.value) 
                                      : e.target.value
                                  })}
                                  placeholder={schema.placeholder}
                                />
                              )}
                              {schema.description && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  {schema.description}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  {errors.actions && (
                    <p className="text-xs text-destructive">{errors.actions}</p>
                  )}
                  
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={addAction}
                    className="w-full"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Action
                  </Button>
                </CardContent>
              </Card>
              
              {/* Guardrails */}
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">Guardrails (Optional)</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  {formData.guardrails.map((guardrail, index) => (
                    <div key={index} className="p-3 border rounded-lg space-y-3">
                      <div className="flex items-center justify-between">
                        <select
                          className="flex-1 px-3 py-2 border rounded-lg mr-2"
                          value={guardrail.type}
                          onChange={e => updateGuardrail(index, 'type', e.target.value)}
                        >
                          {metadata?.guardrails?.map(g => (
                            <option key={g.name} value={g.name}>
                              {g.display_name}
                            </option>
                          ))}
                        </select>
                        <Button
                          size="icon"
                          variant="ghost"
                          onClick={() => removeGuardrail(index)}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                      
                      {/* Dynamic params based on guardrail type */}
                      {metadata?.guardrails?.find(g => g.name === guardrail.type)?.params && (
                        <div className="space-y-2 pl-4">
                          {Object.entries(
                            metadata.guardrails.find(g => g.name === guardrail.type).params
                          ).map(([key, schema]) => (
                            <div key={key}>
                              <label className="block text-xs font-medium mb-1">
                                {schema.display_name || key}
                              </label>
                              <input
                                type={schema.type === 'number' ? 'number' : 'text'}
                                className="w-full px-2 py-1 text-sm border rounded"
                                value={guardrail.params[key] || ''}
                                onChange={e => updateGuardrail(index, 'params', {
                                  ...guardrail.params,
                                  [key]: schema.type === 'number' 
                                    ? parseFloat(e.target.value) 
                                    : e.target.value
                                })}
                                placeholder={schema.placeholder}
                              />
                              {schema.description && (
                                <p className="text-xs text-muted-foreground mt-1">
                                  {schema.description}
                                </p>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                  
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={addGuardrail}
                    className="w-full"
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add Guardrail
                  </Button>
                </CardContent>
              </Card>
            </div>
          ) : (
            /* YAML Mode */
            <div className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">YAML Editor</CardTitle>
                </CardHeader>
                <CardContent>
                  <textarea
                    className={cn(
                      "w-full h-96 px-3 py-2 font-mono text-sm border rounded-lg",
                      errors.rule_yaml && "border-destructive"
                    )}
                    value={formData.rule_yaml}
                    onChange={e => handleChange('rule_yaml', e.target.value)}
                    placeholder={`name: "My Rule"
description: "Description of the rule"
enabled: true
priority: 50
quiet_period_sec: 45

when:
  - filename_pattern:
      pattern: "*.mp4"

do:
  - ffmpeg_remux:
      output_format: "mov"`}
                  />
                  {errors.rule_yaml && (
                    <p className="text-xs text-destructive mt-1">{errors.rule_yaml}</p>
                  )}
                </CardContent>
              </Card>
            </div>
          )}
          
          {/* Test Results */}
          {testResults && (
            <Card className={testResults.error ? 'border-destructive' : 'border-success'}>
              <CardHeader>
                <CardTitle className="text-sm flex items-center gap-2">
                  {testResults.error ? (
                    <>
                      <AlertCircle className="w-4 h-4 text-destructive" />
                      Test Failed
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4 text-success" />
                      Test Passed
                    </>
                  )}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {testResults.error ? (
                  <p className="text-sm text-destructive">{testResults.error}</p>
                ) : (
                  <div className="space-y-2 text-sm">
                    <p>
                      <span className="font-medium">Quiet Period:</span>{' '}
                      {testResults.quiet_period_active ? 'Active' : 'Not active'}
                    </p>
                    <p>
                      <span className="font-medium">Active Hours:</span>{' '}
                      {testResults.active_hours_match ? 'Within schedule' : 'Outside schedule'}
                    </p>
                    <p>
                      <span className="font-medium">Should Execute:</span>{' '}
                      {testResults.should_execute ? 'Yes' : 'No'}
                    </p>
                    {testResults.message && (
                      <p className="text-muted-foreground">{testResults.message}</p>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
        
        {/* Footer */}
        <div className="p-6 border-t border-border">
          <div className="flex items-center justify-between">
            <div className="flex gap-2">
              <Button
                variant="outline"
                onClick={handleTest}
              >
                <Play className="w-4 h-4 mr-2" />
                Test Rule
              </Button>
              <Button
                variant="outline"
                onClick={handleCompile}
              >
                <Code className="w-4 h-4 mr-2" />
                Compile
              </Button>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={onClose}>
                Cancel
              </Button>
              <Button onClick={handleSave}>
                <Save className="w-4 h-4 mr-2" />
                Save Rule
              </Button>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}