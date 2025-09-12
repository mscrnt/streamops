import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/Select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/Table';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/Sheet';
import { Calendar } from '@/components/ui/Calendar';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/Popover';
import { format, subDays } from 'date-fns';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  RefreshCw,
  Filter,
  CalendarIcon,
  ChevronRight,
  AlertCircle,
  Zap
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface AuditEntry {
  id: string;
  created_at: string;
  event: string;
  channel: string;
  status: 'sent' | 'failed' | 'pending' | 'retrying';
  latency_ms?: number;
  provider_msg_id?: string;
  retry_count?: number;
  next_retry_at?: string;
  request?: any;
  response?: any;
  error?: string;
}

export default function AuditTab() {
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedEntry, setSelectedEntry] = useState<AuditEntry | null>(null);
  const [showDetails, setShowDetails] = useState(false);
  
  // Filters
  const [dateRange, setDateRange] = useState({
    from: subDays(new Date(), 7),
    to: new Date(),
  });
  const [channelFilter, setChannelFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [eventFilter, setEventFilter] = useState('');
  
  // Pagination
  const [hasMore, setHasMore] = useState(false);
  const [cursor, setCursor] = useState<string | null>(null);

  useEffect(() => {
    loadAuditLog();
  }, [dateRange, channelFilter, statusFilter, eventFilter]);

  const loadAuditLog = async (append = false) => {
    try {
      const params = new URLSearchParams();
      if (channelFilter !== 'all') params.set('channel', channelFilter);
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (eventFilter) params.set('event', eventFilter);
      if (cursor && append) params.set('cursor', cursor);
      params.set('from', dateRange.from.toISOString());
      params.set('to', dateRange.to.toISOString());
      params.set('limit', '50');

      const response = await fetch(`/api/notifications/audit?${params}`);
      if (response.ok) {
        const data = await response.json();
        if (append) {
          setEntries(prev => [...prev, ...data.entries]);
        } else {
          setEntries(data.entries || []);
        }
        setHasMore(data.has_more || false);
        setCursor(data.next_cursor || null);
      }
    } catch (error) {
      console.error('Failed to load audit log:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'sent':
        return <CheckCircle2 className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'pending':
        return <Clock className="h-4 w-4 text-yellow-500" />;
      case 'retrying':
        return <RefreshCw className="h-4 w-4 text-orange-500 animate-spin" />;
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: any = {
      sent: 'default',
      failed: 'destructive',
      pending: 'secondary',
      retrying: 'secondary',
    };
    return (
      <Badge variant={variants[status] || 'default'}>
        {status}
      </Badge>
    );
  };

  const getChannelIcon = (channel: string) => {
    const icons: { [key: string]: string } = {
      discord: '💬',
      email: '📧',
      twitter: '🐦',
      webhook: '🔗',
    };
    return icons[channel] || '📄';
  };

  const formatLatency = (ms?: number) => {
    if (!ms) return '-';
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Notification Audit Log</CardTitle>
              <CardDescription>
                Track all notification deliveries and failures
              </CardDescription>
            </div>
            <Button 
              variant="outline" 
              size="sm"
              onClick={() => loadAuditLog()}
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Filters */}
          <div className="flex flex-wrap gap-4">
            <div className="flex gap-2">
              <Popover>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    className={cn(
                      "w-[240px] justify-start text-left font-normal",
                      !dateRange && "text-muted-foreground"
                    )}
                  >
                    <CalendarIcon className="mr-2 h-4 w-4" />
                    {dateRange?.from ? (
                      dateRange.to ? (
                        <>
                          {format(dateRange.from, "LLL dd, y")} -{" "}
                          {format(dateRange.to, "LLL dd, y")}
                        </>
                      ) : (
                        format(dateRange.from, "LLL dd, y")
                      )
                    ) : (
                      <span>Pick a date range</span>
                    )}
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-auto p-0" align="start">
                  <Calendar
                    initialFocus
                    mode="range"
                    defaultMonth={dateRange?.from}
                    selected={dateRange}
                    onSelect={(range: any) => setDateRange(range)}
                    numberOfMonths={2}
                  />
                </PopoverContent>
              </Popover>
            </div>

            <Select value={channelFilter} onValueChange={setChannelFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Channels</SelectItem>
                <SelectItem value="discord">Discord</SelectItem>
                <SelectItem value="email">Email</SelectItem>
                <SelectItem value="twitter">Twitter/X</SelectItem>
                <SelectItem value="webhook">Webhooks</SelectItem>
              </SelectContent>
            </Select>

            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger className="w-[150px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="sent">Sent</SelectItem>
                <SelectItem value="failed">Failed</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="retrying">Retrying</SelectItem>
              </SelectContent>
            </Select>

            <Input
              placeholder="Filter by event..."
              value={eventFilter}
              onChange={(e) => setEventFilter(e.target.value)}
              className="w-[200px]"
            />
          </div>

          {/* Audit Table */}
          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Time</TableHead>
                  <TableHead>Event</TableHead>
                  <TableHead>Channel</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                    </TableCell>
                  </TableRow>
                ) : entries.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8 text-muted-foreground">
                      No notification events found
                    </TableCell>
                  </TableRow>
                ) : (
                  entries.map((entry) => (
                    <TableRow 
                      key={entry.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => {
                        setSelectedEntry(entry);
                        setShowDetails(true);
                      }}
                    >
                      <TableCell className="font-mono text-sm">
                        {format(new Date(entry.created_at), 'HH:mm:ss')}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{entry.event}</span>
                          {entry.retry_count && entry.retry_count > 0 && (
                            <Badge variant="outline" className="text-xs">
                              Retry {entry.retry_count}
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <span>{getChannelIcon(entry.channel)}</span>
                          <span>{entry.channel}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          {getStatusIcon(entry.status)}
                          {getStatusBadge(entry.status)}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Zap className="h-3 w-3 text-muted-foreground" />
                          <span className="text-sm">{formatLatency(entry.latency_ms)}</span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>

          {hasMore && (
            <div className="flex justify-center">
              <Button
                variant="outline"
                onClick={() => loadAuditLog(true)}
              >
                Load More
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Details Sheet */}
      <Sheet open={showDetails} onOpenChange={setShowDetails}>
        <SheetContent className="w-[600px] overflow-y-auto">
          <SheetHeader>
            <SheetTitle>Notification Details</SheetTitle>
            <SheetDescription>
              Full details of the notification attempt
            </SheetDescription>
          </SheetHeader>

          {selectedEntry && (
            <div className="mt-6 space-y-6">
              <div className="space-y-2">
                <Label>Event</Label>
                <p className="font-medium">{selectedEntry.event}</p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Channel</Label>
                  <div className="flex items-center gap-2">
                    <span>{getChannelIcon(selectedEntry.channel)}</span>
                    <span>{selectedEntry.channel}</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label>Status</Label>
                  <div className="flex items-center gap-2">
                    {getStatusIcon(selectedEntry.status)}
                    {getStatusBadge(selectedEntry.status)}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Timestamp</Label>
                  <p className="font-mono text-sm">
                    {format(new Date(selectedEntry.created_at), 'PPpp')}
                  </p>
                </div>

                <div className="space-y-2">
                  <Label>Latency</Label>
                  <p className="font-mono text-sm">
                    {formatLatency(selectedEntry.latency_ms)}
                  </p>
                </div>
              </div>

              {selectedEntry.provider_msg_id && (
                <div className="space-y-2">
                  <Label>Provider Message ID</Label>
                  <p className="font-mono text-sm">{selectedEntry.provider_msg_id}</p>
                </div>
              )}

              {selectedEntry.error && (
                <div className="space-y-2">
                  <Label>Error</Label>
                  <div className="p-3 bg-red-50 dark:bg-red-950 rounded-lg">
                    <p className="text-sm text-red-600 dark:text-red-400">
                      {selectedEntry.error}
                    </p>
                  </div>
                </div>
              )}

              {selectedEntry.next_retry_at && (
                <div className="space-y-2">
                  <Label>Next Retry</Label>
                  <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-yellow-500" />
                    <p className="text-sm">
                      {format(new Date(selectedEntry.next_retry_at), 'PPpp')}
                    </p>
                  </div>
                </div>
              )}

              {selectedEntry.request && (
                <div className="space-y-2">
                  <Label>Request (Redacted)</Label>
                  <pre className="p-3 bg-muted rounded-lg overflow-x-auto text-xs">
                    {JSON.stringify(selectedEntry.request, null, 2)}
                  </pre>
                </div>
              )}

              {selectedEntry.response && (
                <div className="space-y-2">
                  <Label>Response</Label>
                  <pre className="p-3 bg-muted rounded-lg overflow-x-auto text-xs">
                    {JSON.stringify(selectedEntry.response, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </SheetContent>
      </Sheet>
    </div>
  );
}