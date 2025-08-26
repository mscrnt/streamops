import { Power, ChevronRight, FileText, Settings } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { cn } from '@/lib/utils'

export default function PresetCard({ preset, onToggle, onViewRules }) {
  const isEnabled = preset.enabled !== false
  
  return (
    <Card className={cn("transition-opacity", !isEnabled && "opacity-60")}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-base flex items-center gap-2">
              {preset.icon && (
                <span className="text-lg">{preset.icon}</span>
              )}
              {preset.name}
            </CardTitle>
            {preset.category && (
              <Badge variant="outline" className="mt-2 text-xs">
                {preset.category}
              </Badge>
            )}
          </div>
          <Button
            size="icon"
            variant="ghost"
            onClick={() => onToggle(!isEnabled)}
            className={cn(
              "transition-colors",
              isEnabled ? "text-success hover:text-success/80" : "text-muted-foreground"
            )}
          >
            <Power className="w-4 h-4" />
          </Button>
        </div>
      </CardHeader>
      
      <CardContent className="space-y-3">
        <p className="text-sm text-muted-foreground">
          {preset.description}
        </p>
        
        {preset.rules && preset.rules.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Included Rules
            </p>
            <ul className="space-y-1">
              {preset.rules.slice(0, 3).map((rule, index) => (
                <li key={index} className="flex items-center text-xs text-muted-foreground">
                  <ChevronRight className="w-3 h-3 mr-1" />
                  {rule.name || rule}
                </li>
              ))}
              {preset.rules.length > 3 && (
                <li className="text-xs text-muted-foreground ml-4">
                  +{preset.rules.length - 3} more
                </li>
              )}
            </ul>
          </div>
        )}
        
        {preset.tags && preset.tags.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {preset.tags.map(tag => (
              <Badge key={tag} variant="secondary" className="text-xs">
                {tag}
              </Badge>
            ))}
          </div>
        )}
        
        <div className="flex items-center justify-between pt-2 border-t">
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {preset.rule_count && (
              <span className="flex items-center gap-1">
                <FileText className="w-3 h-3" />
                {preset.rule_count} rules
              </span>
            )}
            {preset.priority && (
              <span className="flex items-center gap-1">
                <Settings className="w-3 h-3" />
                Priority {preset.priority}
              </span>
            )}
          </div>
          
          {onViewRules && (
            <Button
              size="sm"
              variant="ghost"
              onClick={onViewRules}
              className="h-7 text-xs"
            >
              View Rules
              <ChevronRight className="w-3 h-3 ml-1" />
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  )
}