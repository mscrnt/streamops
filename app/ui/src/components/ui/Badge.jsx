import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const badgeVariants = {
  variant: {
    default: 'border-transparent bg-primary text-primary-foreground hover:bg-primary/80',
    secondary: 'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80',
    destructive: 'border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80',
    outline: 'text-foreground border-border',
    success: 'border-transparent bg-green-500 text-white hover:bg-green-600',
    warning: 'border-transparent bg-yellow-500 text-white hover:bg-yellow-600',
  },
}

const Badge = forwardRef(({ 
  className, 
  variant = 'default',
  ...props 
}, ref) => {
  return (
    <div
      ref={ref}
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
        badgeVariants.variant[variant],
        className
      )}
      {...props}
    />
  )
})
Badge.displayName = 'Badge'

// Status-specific badge components for common use cases
const StatusBadge = ({ status, ...props }) => {
  const getVariant = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed':
      case 'success':
      case 'online':
      case 'active':
        return 'success'
      case 'failed':
      case 'error':
      case 'offline':
        return 'destructive'
      case 'pending':
      case 'waiting':
      case 'paused':
        return 'warning'
      case 'running':
      case 'processing':
        return 'default'
      default:
        return 'secondary'
    }
  }

  return (
    <Badge 
      variant={getVariant(status)} 
      {...props}
    >
      {status}
    </Badge>
  )
}

export { Badge, StatusBadge }
export default Badge