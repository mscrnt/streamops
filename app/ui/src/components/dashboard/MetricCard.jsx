import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card'

export default function MetricCard({ 
  title, 
  value, 
  subvalue, 
  icon: Icon, 
  trend, 
  variant = 'default' 
}) {
  // Simple sparkline from trend data
  const renderSparkline = () => {
    if (!trend || trend.length === 0) return null
    
    const values = trend.map(t => t.v)
    const max = Math.max(...values)
    const min = Math.min(...values)
    const range = max - min || 1
    
    // Create SVG path
    const width = 80
    const height = 20
    const points = values.map((v, i) => {
      const x = (i / (values.length - 1)) * width
      const y = height - ((v - min) / range) * height
      return `${x},${y}`
    }).join(' ')
    
    return (
      <svg width={width} height={height} className="opacity-50">
        <polyline
          points={points}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
        />
      </svg>
    )
  }
  
  const variantClasses = {
    default: '',
    primary: 'border-primary/50',
    secondary: 'border-secondary/50',
    warning: 'border-yellow-500/50 bg-yellow-500/5',
    destructive: 'border-red-500/50 bg-red-500/5'
  }
  
  return (
    <Card className={variantClasses[variant]}>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subvalue && (
          <p className="text-xs text-muted-foreground mt-1">
            {subvalue}
          </p>
        )}
        {trend && trend.length > 0 && (
          <div className="mt-2">
            {renderSparkline()}
          </div>
        )}
      </CardContent>
    </Card>
  )
}