import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const Input = forwardRef(({ 
  className, 
  type = 'text',
  error,
  ...props 
}, ref) => {
  return (
    <input
      type={type}
      className={cn(
        'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        error && 'border-destructive focus-visible:ring-destructive',
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Input.displayName = 'Input'

// Textarea component
export const Textarea = forwardRef(({ 
  className,
  error,
  ...props 
}, ref) => {
  return (
    <textarea
      className={cn(
        'flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
        error && 'border-destructive focus-visible:ring-destructive',
        className
      )}
      ref={ref}
      {...props}
    />
  )
})
Textarea.displayName = 'Textarea'

// Label component
export const Label = forwardRef(({ 
  className,
  ...props 
}, ref) => (
  <label
    ref={ref}
    className={cn(
      'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70',
      className
    )}
    {...props}
  />
))
Label.displayName = 'Label'

// FormField component for consistent form styling
export const FormField = ({ 
  label, 
  error, 
  children, 
  className,
  required = false 
}) => (
  <div className={cn('space-y-2', className)}>
    {label && (
      <Label className={error ? 'text-destructive' : ''}>
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
    )}
    {children}
    {error && (
      <p className="text-sm text-destructive">{error}</p>
    )}
  </div>
)

export { Input }
export default Input