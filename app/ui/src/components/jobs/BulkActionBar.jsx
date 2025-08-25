import { RefreshCw, X, Trash2, CheckSquare } from 'lucide-react'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export default function BulkActionBar({ 
  selectedCount, 
  onAction, 
  onClear 
}) {
  return (
    <div className="border-b border-border bg-accent/50 p-4 animate-in slide-in-from-top duration-200">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Badge variant="secondary" className="text-sm">
            <CheckSquare className="w-4 h-4 mr-1" />
            {selectedCount} selected
          </Badge>
          
          <Button 
            size="sm" 
            variant="ghost"
            onClick={onClear}
          >
            <X className="w-4 h-4 mr-1" />
            Clear
          </Button>
        </div>
        
        <div className="flex items-center gap-2">
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('retry')}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Retry Failed
          </Button>
          
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('cancel')}
          >
            <X className="w-4 h-4 mr-2" />
            Cancel Running
          </Button>
          
          <div className="ml-2 h-6 w-px bg-border" />
          
          <Button 
            size="sm" 
            variant="destructive"
            onClick={() => onAction('delete')}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Records
          </Button>
        </div>
      </div>
    </div>
  )
}