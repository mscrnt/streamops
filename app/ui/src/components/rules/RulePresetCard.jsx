import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'
import { Wand2, ChevronRight } from 'lucide-react'

export default function RulePresetCard({ preset, onSelect }) {
  // Map category to color
  const categoryColors = {
    processing: 'blue',
    organization: 'green',
    export: 'purple'
  }
  
  const color = categoryColors[preset.category] || 'gray'
  
  return (
    <Card className="hover:shadow-lg transition-shadow cursor-pointer" onClick={() => onSelect(preset)}>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle className="text-lg">{preset.label}</CardTitle>
            <Badge variant="secondary" className="mt-2">
              {preset.category}
            </Badge>
          </div>
          <Wand2 className="h-5 w-5 text-muted-foreground" />
        </div>
      </CardHeader>
      <CardContent>
        <CardDescription className="mb-4">
          {preset.description}
        </CardDescription>
        
        {/* Show key parameters */}
        <div className="space-y-2 mb-4">
          {preset.defaults && Object.entries(preset.defaults).slice(0, 3).map(([key, value]) => (
            <div key={key} className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}:
              </span>
              <span className="font-medium">
                {typeof value === 'boolean' ? (value ? 'Yes' : 'No') : value}
              </span>
            </div>
          ))}
        </div>
        
        <Button className="w-full" variant="outline">
          Use This Preset
          <ChevronRight className="h-4 w-4 ml-2" />
        </Button>
      </CardContent>
    </Card>
  )
}