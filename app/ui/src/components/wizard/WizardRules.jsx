import { useState, useEffect } from 'react'
import { 
  Wand2, 
  Check, 
  Settings,
  Info,
  ChevronDown,
  ChevronUp
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import { SimpleSelect } from '@/components/ui/Select'

export default function WizardRules({ data = [], onChange, defaults }) {
  const [rules, setRules] = useState(() => {
    if (data.length > 0) return data
    
    // Initialize with defaults
    return defaults?.rules?.map(r => ({
      ...r,
      enabled: r.enabled_by_default !== false,
      parameters: { ...r.parameters }
    })) || []
  })
  
  const [expandedRule, setExpandedRule] = useState(null)
  
  useEffect(() => {
    onChange(rules)
  }, [rules])
  
  const toggleRule = (ruleId) => {
    setRules(prev => prev.map(r => 
      r.id === ruleId ? { ...r, enabled: !r.enabled } : r
    ))
  }
  
  const updateRuleParameter = (ruleId, param, value) => {
    setRules(prev => prev.map(r => 
      r.id === ruleId ? { 
        ...r, 
        parameters: { ...r.parameters, [param]: value }
      } : r
    ))
  }
  
  const renderParameterInput = (rule, param, schema) => {
    const value = rule.parameters[param] ?? schema.default
    
    if (schema.type === 'boolean') {
      return (
        <input
          type="checkbox"
          checked={value}
          onChange={(e) => updateRuleParameter(rule.id, param, e.target.checked)}
          className="ml-auto"
        />
      )
    } else if (schema.type === 'string' && schema.enum) {
      return (
        <SimpleSelect
          value={value}
          onChange={(val) => updateRuleParameter(rule.id, param, val)}
          className="ml-auto w-32"
        >
          {schema.enum.map(opt => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </SimpleSelect>
      )
    } else if (schema.type === 'integer' || schema.type === 'number') {
      return (
        <Input
          type="number"
          value={value}
          onChange={(e) => updateRuleParameter(rule.id, param, parseFloat(e.target.value))}
          min={schema.minimum}
          max={schema.maximum}
          className="ml-auto w-24"
        />
      )
    } else if (schema.format === 'path') {
      // This would be populated from drives selected in previous step
      return (
        <Input
          type="text"
          value={value || '/mnt/editing'}
          onChange={(e) => updateRuleParameter(rule.id, param, e.target.value)}
          className="ml-auto w-48"
          placeholder="Select path..."
        />
      )
    } else {
      return (
        <Input
          type="text"
          value={value}
          onChange={(e) => updateRuleParameter(rule.id, param, e.target.value)}
          className="ml-auto w-48"
        />
      )
    }
  }
  
  const enabledCount = rules.filter(r => r.enabled).length
  
  return (
    <div className="space-y-6">
      {/* Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            Recommended Automations
            <Badge variant="secondary">
              {enabledCount} of {rules.length} enabled
            </Badge>
          </CardTitle>
          <CardDescription>
            These safe defaults will process your recordings automatically. 
            You can customize them now or change them later.
          </CardDescription>
        </CardHeader>
      </Card>
      
      {/* Rule Cards */}
      <div className="space-y-4">
        {rules.map(rule => {
          const isExpanded = expandedRule === rule.id
          const hasRequiredParams = rule.parameters_schema?.required?.length > 0
          
          return (
            <Card 
              key={rule.id} 
              className={rule.enabled ? 'border-primary/50' : 'opacity-75'}
            >
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <CardTitle className="text-lg flex items-center space-x-2">
                      <Wand2 className="h-5 w-5 text-primary" />
                      <span>{rule.label}</span>
                    </CardTitle>
                    <CardDescription className="mt-2">
                      {rule.description}
                    </CardDescription>
                  </div>
                  <div className="flex items-center space-x-2">
                    {hasRequiredParams && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setExpandedRule(isExpanded ? null : rule.id)}
                      >
                        <Settings className="h-4 w-4 mr-2" />
                        Configure
                        {isExpanded ? (
                          <ChevronUp className="h-4 w-4 ml-2" />
                        ) : (
                          <ChevronDown className="h-4 w-4 ml-2" />
                        )}
                      </Button>
                    )}
                    <Button
                      variant={rule.enabled ? 'default' : 'outline'}
                      onClick={() => toggleRule(rule.id)}
                    >
                      {rule.enabled ? (
                        <>
                          <Check className="h-4 w-4 mr-2" />
                          Enabled
                        </>
                      ) : (
                        <>Enable</>
                      )}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              
              {isExpanded && rule.parameters_schema && (
                <CardContent>
                  <div className="space-y-3 p-4 bg-muted/30 rounded-lg">
                    {Object.entries(rule.parameters_schema.properties || {}).map(([param, schema]) => (
                      <div key={param} className="flex items-center justify-between">
                        <div className="flex items-center space-x-2">
                          <label className="text-sm font-medium">
                            {schema.title || param}
                            {rule.parameters_schema.required?.includes(param) && (
                              <span className="text-red-500 ml-1">*</span>
                            )}
                          </label>
                          {schema.description && (
                            <Info className="h-3 w-3 text-muted-foreground" title={schema.description} />
                          )}
                        </div>
                        {renderParameterInput(rule, param, schema)}
                      </div>
                    ))}
                  </div>
                  
                  {/* Show defaults */}
                  <div className="mt-4 p-3 bg-blue-500/10 rounded-lg">
                    <p className="text-xs text-blue-600 dark:text-blue-400">
                      <Info className="h-3 w-3 inline mr-1" />
                      These settings can be changed anytime from the Rules page
                    </p>
                  </div>
                </CardContent>
              )}
            </Card>
          )
        })}
      </div>
      
      {/* Info */}
      <Card className="border-green-500/50 bg-green-500/10">
        <CardContent className="py-4">
          <div className="flex items-start space-x-3">
            <Check className="h-5 w-5 text-green-500 mt-0.5" />
            <div>
              <p className="font-medium">Safe by Default</p>
              <p className="text-sm text-muted-foreground">
                All rules include guardrails that pause processing while you're recording or streaming.
                Heavy jobs won't interfere with your live content.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}