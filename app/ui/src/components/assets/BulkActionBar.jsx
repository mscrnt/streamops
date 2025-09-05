import { 
  RefreshCw, Play, Film, Move, Archive, Trash2, 
  CheckSquare, X 
} from 'lucide-react'
import Button from '@/components/ui/Button'
import { Badge } from '@/components/ui/Badge'

export default function BulkActionBar({ 
  selectedCount, 
  onAction, 
  onSelectAll, 
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
          
          <div className="flex items-center gap-2">
            <Button 
              size="sm" 
              variant="ghost"
              onClick={onSelectAll}
            >
              Select all on page
            </Button>
            
            <Button 
              size="sm" 
              variant="ghost"
              onClick={onClear}
            >
              <X className="w-4 h-4 mr-1" />
              Clear
            </Button>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('remux')}
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Remux
          </Button>
          
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('proxy')}
          >
            <Play className="w-4 h-4 mr-2" />
            Proxy
          </Button>
          
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('move')}
          >
            <Move className="w-4 h-4 mr-2" />
            Move
          </Button>
          
          <Button 
            size="sm"
            variant="outline"
            onClick={() => onAction('archive')}
          >
            <Archive className="w-4 h-4 mr-2" />
            Archive
          </Button>
          
          <div className="ml-2 h-6 w-px bg-border" />
          
          <Button 
            size="sm" 
            variant="destructive"
            onClick={() => onAction('delete')}
          >
            <Trash2 className="w-4 h-4 mr-2" />
            Delete
          </Button>
        </div>
      </div>
    </div>
  )
}