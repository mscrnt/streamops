import { useState, useEffect, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  FileText, 
  Search, 
  Filter, 
  Download, 
  RefreshCw,
  AlertCircle,
  Info,
  AlertTriangle,
  XCircle,
  Bug,
  X,
  ChevronDown
} from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import { Badge } from '@/components/ui/Badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/Select'
import { useApi } from '@/hooks/useApi'
import { cn } from '@/lib/utils'

const LOG_LEVELS = {
  DEBUG: { 
    icon: Bug, 
    color: 'text-gray-500 dark:text-gray-400', 
    bg: 'bg-gray-50 dark:bg-gray-900/50 border-gray-200 dark:border-gray-800' 
  },
  INFO: { 
    icon: Info, 
    color: 'text-blue-500 dark:text-blue-400', 
    bg: 'bg-blue-50 dark:bg-blue-950/50 border-blue-200 dark:border-blue-900' 
  },
  WARNING: { 
    icon: AlertTriangle, 
    color: 'text-yellow-600 dark:text-yellow-400', 
    bg: 'bg-yellow-50 dark:bg-yellow-950/50 border-yellow-200 dark:border-yellow-900' 
  },
  ERROR: { 
    icon: XCircle, 
    color: 'text-red-500 dark:text-red-400', 
    bg: 'bg-red-50 dark:bg-red-950/50 border-red-200 dark:border-red-900' 
  },
  CRITICAL: { 
    icon: AlertCircle, 
    color: 'text-red-700 dark:text-red-500', 
    bg: 'bg-red-100 dark:bg-red-950/70 border-red-300 dark:border-red-800' 
  }
}

function LogEntry({ entry }) {
  const level = entry.level?.toUpperCase() || 'INFO'
  const levelConfig = LOG_LEVELS[level] || LOG_LEVELS.INFO
  const Icon = levelConfig.icon

  return (
    <div className={cn(
      "p-3 rounded-lg border transition-colors hover:bg-gray-100 dark:hover:bg-gray-800/50",
      levelConfig.bg
    )}>
      <div className="flex items-start gap-3">
        <Icon className={cn("w-4 h-4 mt-0.5 flex-shrink-0", levelConfig.color)} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <Badge variant="outline" className="text-xs">
              {level}
            </Badge>
            {entry.timestamp && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {(() => {
                  // Parse various timestamp formats
                  const ts = entry.timestamp
                  let date
                  
                  // Try parsing as ISO date with dot for milliseconds (2024-01-15 10:30:45.330)
                  if (ts.includes(' ') && ts.includes('.')) {
                    date = new Date(ts.replace(' ', 'T'))
                  }
                  // Try parsing as date with comma for milliseconds (2024-01-15 10:30:45,330)
                  else if (ts.includes(' ') && ts.includes(',')) {
                    date = new Date(ts.replace(',', '.').replace(' ', 'T'))
                  }
                  // Try parsing as regular date string
                  else {
                    date = new Date(ts)
                  }
                  
                  return isNaN(date.getTime()) ? ts : date.toLocaleString()
                })()}
              </span>
            )}
            {entry.module && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                {entry.module}
              </span>
            )}
          </div>
          <p className="text-sm text-gray-700 dark:text-gray-300 break-words whitespace-pre-wrap">
            {entry.message}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function LogsViewer({ open, onClose }) {
  const { api } = useApi()
  const [selectedFile, setSelectedFile] = useState('api.log')
  const [levelFilter, setLevelFilter] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [autoRefresh, setAutoRefresh] = useState(false)

  // Fetch available log files
  const { data: files = [], refetch: refetchFiles } = useQuery({
    queryKey: ['logs', 'files'],
    queryFn: async () => {
      const response = await api.get('/logs/files')
      return response.data
    },
    enabled: open
  })

  // Fetch log entries
  const { 
    data: logsData, 
    isLoading, 
    error,
    refetch: refetchLogs 
  } = useQuery({
    queryKey: ['logs', 'read', selectedFile, levelFilter, searchQuery],
    queryFn: async () => {
      const params = {
        file: selectedFile,
        limit: 500
      }
      if (levelFilter) params.level = levelFilter
      if (searchQuery) params.search = searchQuery
      
      const response = await api.get('/logs/read', { params })
      return response.data
    },
    enabled: open && !!selectedFile,
    refetchInterval: autoRefresh ? 5000 : false
  })

  // Auto-refresh effect
  useEffect(() => {
    if (autoRefresh && open) {
      const interval = setInterval(() => {
        refetchLogs()
      }, 5000)
      return () => clearInterval(interval)
    }
  }, [autoRefresh, open, refetchLogs])

  const handleDownload = useCallback(() => {
    if (!logsData?.entries) return
    
    const content = logsData.entries.map(entry => entry.raw).join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = selectedFile
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }, [logsData, selectedFile])

  const handleClearLog = useCallback(async () => {
    if (!selectedFile) return
    if (!confirm(`Are you sure you want to clear ${selectedFile}?`)) return
    
    try {
      await api.delete('/logs/clear', { params: { file: selectedFile } })
      refetchLogs()
    } catch (error) {
      console.error('Failed to clear log:', error)
    }
  }, [selectedFile, api, refetchLogs])

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-6xl h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <FileText className="w-5 h-5" />
            System Logs
          </DialogTitle>
          <DialogDescription>
            View and search through system log files
          </DialogDescription>
        </DialogHeader>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 py-3 border-b">
          {/* File selector */}
          <Select value={selectedFile} onValueChange={setSelectedFile}>
            <SelectTrigger className="w-full sm:w-[200px]">
              <SelectValue placeholder="Select log file" />
            </SelectTrigger>
            <SelectContent>
              {files.map(file => (
                <SelectItem key={file.name} value={file.name}>
                  <div className="flex items-center justify-between w-full">
                    <span>{file.name}</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                      {(file.size / 1024).toFixed(1)}KB
                    </span>
                  </div>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Level filter */}
          <Select value={levelFilter || "ALL"} onValueChange={(value) => setLevelFilter(value === "ALL" ? "" : value)}>
            <SelectTrigger className="w-full sm:w-[150px]">
              <SelectValue placeholder="All levels" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="ALL">All levels</SelectItem>
              <SelectItem value="DEBUG">Debug</SelectItem>
              <SelectItem value="INFO">Info</SelectItem>
              <SelectItem value="WARNING">Warning</SelectItem>
              <SelectItem value="ERROR">Error</SelectItem>
              <SelectItem value="CRITICAL">Critical</SelectItem>
            </SelectContent>
          </Select>

          {/* Search */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <Input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10"
            />
          </div>

          {/* Actions */}
          <div className="flex gap-2">
            <Button
              variant={autoRefresh ? "default" : "outline"}
              size="sm"
              onClick={() => setAutoRefresh(!autoRefresh)}
              title={autoRefresh ? "Stop auto-refresh" : "Start auto-refresh"}
            >
              <RefreshCw className={cn(
                "w-4 h-4",
                autoRefresh && "animate-spin"
              )} />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={refetchLogs}
              title="Refresh now"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={!logsData?.entries?.length}
              title="Download log file"
            >
              <Download className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearLog}
              className="text-red-600 hover:text-red-700"
              title="Clear log file"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* Stats bar */}
        {logsData && (
          <div className="flex items-center gap-4 py-2 text-sm text-gray-600 dark:text-gray-400">
            <span>
              Showing {logsData.entries?.length || 0} of {logsData.filtered} entries
            </span>
            <span className="text-gray-400 dark:text-gray-600">•</span>
            <span>
              Total: {logsData.total} lines
            </span>
            {selectedFile && files.find(f => f.name === selectedFile) && (
              <>
                <span className="text-gray-400 dark:text-gray-600">•</span>
                <span>
                  Modified: {new Date(files.find(f => f.name === selectedFile).modified).toLocaleString()}
                </span>
              </>
            )}
          </div>
        )}

        {/* Log entries */}
        <div className="flex-1 overflow-y-auto space-y-2 p-4 bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-800">
          {isLoading && (
            <div className="flex items-center justify-center h-full">
              <RefreshCw className="w-6 h-6 animate-spin text-gray-400" />
            </div>
          )}
          
          {error && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <AlertCircle className="w-12 h-12 text-red-500 dark:text-red-400 mx-auto mb-2" />
                <p className="text-red-600 dark:text-red-400">Failed to load logs</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">{error.message}</p>
              </div>
            </div>
          )}
          
          {!isLoading && !error && logsData?.entries?.length === 0 && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <FileText className="w-12 h-12 text-gray-400 dark:text-gray-600 mx-auto mb-2" />
                <p className="text-gray-600 dark:text-gray-400">No log entries found</p>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                  {searchQuery || levelFilter ? 'Try adjusting your filters' : 'This log file is empty'}
                </p>
              </div>
            </div>
          )}
          
          {!isLoading && !error && logsData?.entries?.map((entry, index) => (
            <LogEntry key={index} entry={entry} />
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}