import { useMemo } from 'react'
import { useJobStats } from '@/hooks/useJobStats'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'

export default function JobStatsMini() {
  const { data: stats, isLoading } = useJobStats({ window: '24h' })
  
  const chartData = useMemo(() => {
    if (!stats) return []
    return [
      { name: 'Completed', value: stats.completed || 0, color: '#10b981' },
      { name: 'Failed', value: stats.failed || 0, color: '#ef4444' },
    ]
  }, [stats])
  
  const total = chartData.reduce((sum, item) => sum + item.value, 0)
  const successRate = total > 0 ? Math.round((chartData[0].value / total) * 100) : 0
  
  const avgDuration = stats?.avg_duration ? 
    `${Math.round(stats.avg_duration / 60)}m ${Math.round(stats.avg_duration % 60)}s` : 
    'N/A'
  
  if (isLoading) {
    return (
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-semibold mb-3">Job Statistics (24h)</h3>
        <div className="animate-pulse space-y-3">
          <div className="h-24 bg-muted rounded"></div>
          <div className="h-4 bg-muted rounded w-2/3"></div>
        </div>
      </div>
    )
  }
  
  return (
    <div className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold mb-3">Job Statistics (24h)</h3>
      
      {total === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-muted-foreground">No jobs in the last 24 hours</p>
        </div>
      ) : (
        <div className="space-y-3">
          {/* Compact donut chart */}
          <div className="flex items-center gap-4">
            <div className="relative">
              <ResponsiveContainer width={80} height={80}>
                <PieChart>
                  <Pie
                    data={chartData}
                    cx="50%"
                    cy="50%"
                    innerRadius={25}
                    outerRadius={35}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {chartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip 
                    formatter={(value) => value}
                    contentStyle={{ 
                      backgroundColor: 'hsl(var(--popover))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '6px'
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-sm font-semibold">{successRate}%</span>
              </div>
            </div>
            
            {/* Legend */}
            <div className="flex-1 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-emerald-500"></div>
                  <span className="text-sm">Completed</span>
                </div>
                <span className="text-sm font-medium">{stats?.completed || 0}</span>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <span className="text-sm">Failed</span>
                </div>
                <span className="text-sm font-medium">{stats?.failed || 0}</span>
              </div>
            </div>
          </div>
          
          {/* Additional stats */}
          <div className="pt-3 border-t">
            <div className="flex items-center justify-between">
              <span className="text-xs text-muted-foreground">Avg Duration</span>
              <span className="text-xs font-medium">{avgDuration}</span>
            </div>
            {stats?.queued !== undefined && stats.queued > 0 && (
              <div className="flex items-center justify-between mt-1">
                <span className="text-xs text-muted-foreground">Queued</span>
                <span className="text-xs font-medium">{stats.queued}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}