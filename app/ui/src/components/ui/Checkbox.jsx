import { forwardRef, useState, useEffect } from 'react'
import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

const Checkbox = forwardRef(({ 
  className, 
  checked: controlledChecked,
  defaultChecked = false,
  onCheckedChange,
  disabled = false,
  ...props 
}, ref) => {
  const isControlled = controlledChecked !== undefined
  const [internalChecked, setInternalChecked] = useState(defaultChecked)
  
  const checked = isControlled ? controlledChecked : internalChecked
  
  const handleClick = () => {
    if (disabled) return
    
    const newChecked = !checked
    
    if (!isControlled) {
      setInternalChecked(newChecked)
    }
    
    if (onCheckedChange) {
      onCheckedChange(newChecked)
    }
  }
  
  return (
    <button
      ref={ref}
      type="button"
      role="checkbox"
      aria-checked={checked}
      disabled={disabled}
      onClick={handleClick}
      className={cn(
        "peer h-4 w-4 shrink-0 rounded-sm border border-input bg-background shadow-sm",
        "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground",
        checked && "bg-primary text-primary-foreground border-primary",
        className
      )}
      data-state={checked ? "checked" : "unchecked"}
      {...props}
    >
      {checked && (
        <span className="flex items-center justify-center">
          <Check className="h-3 w-3" />
        </span>
      )}
    </button>
  )
})

Checkbox.displayName = 'Checkbox'

export { Checkbox }
export default Checkbox