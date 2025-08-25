import { 
  CheckCircle, 
  XCircle, 
  Clock, 
  TrendingUp,
  TrendingDown,
  BarChart3,
  FileText
} from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card'
import Button from '@/components/ui/Button'
import { formatDuration } from '@/lib/utils'

export default function JobStatsCard({ stats, timeRange, onOpenReport }) {
  // Calculate success rate
  const successRate = stats.total > 0 
    ? Math.round((stats.completed / stats.total) * 100)
    : 100
  
  // Determine trend based on failure rate
  const failureRate = stats.total > 0 
    ? Math.round((stats.failed / stats.total) * 100)
    : 0
  
  // Format average duration
  const avgDurationFormatted = stats.avgDuration 
    ? formatDuration(0, stats.avgDuration * 1000)
    : 'N/A'
  
  // Get success rate color
  const getSuccessRateColor = () => {
    if (successRate >= 95) return 'text-green-500'
    if (successRate >= 80) return 'text-yellow-500'
    return 'text-red-500'
  }
  
  // Get trend icon
  const getTrendIcon = () => {
    if (failureRate === 0) return <TrendingUp className="h-4 w-4 text-green-500" />
    if (failureRate < 5) return <TrendingUp className="h-4 w-4 text-yellow-500" />
    return <TrendingDown className="h-4 w-4 text-red-500" />
  }
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle>Job Statistics</CardTitle>
            <CardDescription>
              Performance over {timeRange === '24h' ? 'last 24 hours' : timeRange}
            </CardDescription>
          </div>
          <Button 
            variant="outline" 
            size="sm"
            onClick={onOpenReport}
          >
            <FileText className="h-4 w-4 mr-1" />
            Report
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {/* Success Rate Circle */}
        <div className="flex items-center justify-center mb-6">
          <div className="relative">
            <svg className="w-32 h-32 transform -rotate-90">
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="12"
                fill="none"
                className="text-secondary"
              />
              <circle
                cx="64"
                cy="64"
                r="56"
                stroke="currentColor"
                strokeWidth="12"
                fill="none"
                strokeDasharray={`${2 * Math.PI * 56}`}
                strokeDashoffset={`${2 * Math.PI * 56 * (1 - successRate / 100)}`}
                className={`transition-all duration-500 ${getSuccessRateColor()}`}
                strokeLinecap="round"
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-3xl font-bold ${getSuccessRateColor()}`}>
                {successRate}%
              </span>
              <span className="text-xs text-muted-foreground">Success Rate</span>
            </div>
          </div>
        </div>
        
        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-4 mb-4">
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
              <span className="text-sm font-medium">Completed</span>
            </div>
            <p className="text-2xl font-bold">{stats.completed}</p>
            <p className="text-xs text-muted-foreground">
              {stats.total > 0 
                ? `${Math.round((stats.completed / stats.total) * 100)}% of total`
                : 'No jobs'}
            </p>
          </div>
          
          <div className="space-y-1">
            <div className="flex items-center space-x-2">
              <XCircle className="h-4 w-4 text-red-500" />
              <span className="text-sm font-medium">Failed</span>
            </div>
            <p className="text-2xl font-bold">{stats.failed}</p>
            <p className="text-xs text-muted-foreground">
              {stats.total > 0 
                ? `${Math.round((stats.failed / stats.total) * 100)}% of total`
                : 'No failures'}
            </p>
          </div>
        </div>
        
        {/* Average Duration */}
        <div className="border-t pt-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center space-x-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">Avg Duration</span>
            </div>
            {getTrendIcon()}
          </div>
          <p className="text-lg font-semibold">{avgDurationFormatted}</p>
          <p className="text-xs text-muted-foreground">
            Based on {stats.completed} completed jobs
          </p>
        </div>
        
        {/* Performance Indicator */}
        {stats.total > 10 && (
          <div className="mt-4 p-3 rounded-lg bg-secondary/50">
            <div className="flex items-start space-x-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground mt-0.5" />
              <div className="flex-1">
                <p className="text-xs font-medium">Performance</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {successRate >= 95 
                    ? 'Excellent performance with minimal failures'
                    : successRate >= 80
                    ? 'Good performance, monitor failed jobs'
                    : 'Performance issues detected, review failed jobs'}
                </p>
              </div>
            </div>
          </div>
        )}
        
        {/* Empty State */}
        {stats.total === 0 && (
          <div className="text-center py-4">
            <BarChart3 className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
            <p className="text-sm text-muted-foreground">
              No job data available for this period
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  )
}