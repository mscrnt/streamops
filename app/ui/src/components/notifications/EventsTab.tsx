import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Checkbox } from '@/components/ui/Checkbox';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Badge } from '@/components/ui/Badge';
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
import { CheckCircle2, XCircle, AlertCircle, Info } from 'lucide-react';

interface EventsTabProps {
  settings: any;
  onChange: (updates: any) => void;
}

const EVENT_CATEGORIES = {
  job: { label: 'Jobs', icon: '⚙️' },
  recording: { label: 'Recording', icon: '🎥' },
  stream: { label: 'Streaming', icon: '📡' },
  obs: { label: 'OBS', icon: '🎬' },
  system: { label: 'System', icon: '💻' },
};

const EVENTS = {
  // Job events
  'job.started': { category: 'job', label: 'Job Started', severity: 'info' },
  'job.completed': { category: 'job', label: 'Job Completed', severity: 'info' },
  'job.failed': { category: 'job', label: 'Job Failed', severity: 'error' },
  
  // Recording events
  'recording.created': { category: 'recording', label: 'Recording Created', severity: 'info' },
  'recording.started': { category: 'recording', label: 'Recording Started', severity: 'info' },
  'recording.stopped': { category: 'recording', label: 'Recording Stopped', severity: 'info' },
  'recording.processed': { category: 'recording', label: 'Recording Processed', severity: 'info' },
  'recording.failed': { category: 'recording', label: 'Recording Failed', severity: 'error' },
  
  // Streaming events
  'stream.started': { category: 'stream', label: 'Stream Started', severity: 'info' },
  'stream.stopped': { category: 'stream', label: 'Stream Stopped', severity: 'info' },
  'stream.health_warning': { category: 'stream', label: 'Stream Health Warning', severity: 'warning' },
  'stream.health_critical': { category: 'stream', label: 'Stream Health Critical', severity: 'error' },
  'stream.disconnected': { category: 'stream', label: 'Stream Disconnected', severity: 'error' },
  'stream.reconnected': { category: 'stream', label: 'Stream Reconnected', severity: 'info' },
  
  // OBS events
  'obs.connected': { category: 'obs', label: 'OBS Connected', severity: 'info' },
  'obs.disconnected': { category: 'obs', label: 'OBS Disconnected', severity: 'warning' },
  'obs.scene_changed': { category: 'obs', label: 'Scene Changed', severity: 'info' },
  'obs.recording_started': { category: 'obs', label: 'OBS Recording Started', severity: 'info' },
  'obs.recording_stopped': { category: 'obs', label: 'OBS Recording Stopped', severity: 'info' },
  'obs.streaming_started': { category: 'obs', label: 'OBS Streaming Started', severity: 'info' },
  'obs.streaming_stopped': { category: 'obs', label: 'OBS Streaming Stopped', severity: 'info' },
  
  // System events
  'system.alert': { category: 'system', label: 'System Alert', severity: 'warning' },
  'storage.threshold': { category: 'system', label: 'Storage Threshold', severity: 'warning' },
  'drive.offline': { category: 'system', label: 'Drive Offline', severity: 'error' },
};

const CHANNELS = [
  { id: 'discord', label: 'Discord', icon: '💬' },
  { id: 'email', label: 'Email', icon: '📧' },
  { id: 'twitter', label: 'Twitter/X', icon: '🐦' },
  { id: 'webhook', label: 'Webhooks', icon: '🔗' },
];

export default function EventsTab({ settings, onChange }: EventsTabProps) {
  const [categoryFilter, setCategoryFilter] = useState('all');
  const [severityFilter, setSeverityFilter] = useState('all');
  const [templates, setTemplates] = useState<any[]>([]);

  useEffect(() => {
    loadTemplates();
  }, []);

  const loadTemplates = async () => {
    try {
      const response = await fetch('/api/notifications/templates');
      if (response.ok) {
        const data = await response.json();
        setTemplates(data.templates || []);
      }
    } catch (error) {
      console.error('Failed to load templates:', error);
    }
  };

  const getEventKey = (event: string) => {
    return `events_${event.replace(/\./g, '_')}`;
  };

  const isEventEnabled = (event: string, channel: string) => {
    const eventKey = getEventKey(event);
    // Check if the channel is enabled for this event
    if (channel === 'discord') {
      return settings[eventKey] && settings.discord_enabled;
    } else if (channel === 'email') {
      return settings[eventKey] && settings.email_enabled;
    } else if (channel === 'twitter') {
      return settings[eventKey] && settings.twitter_enabled;
    } else if (channel === 'webhook') {
      return settings[eventKey] && settings.webhook_enabled;
    }
    return false;
  };

  const toggleEvent = (event: string, channel: string, enabled: boolean) => {
    // For now, we're using the simple event flags from settings
    // In a full implementation, we'd have a more complex event routing system
    const eventKey = getEventKey(event);
    
    // Just toggle the event flag for now
    // A full implementation would maintain channel-specific subscriptions
    onChange({ [eventKey]: enabled });
  };

  const enableAll = () => {
    const updates: any = {};
    Object.keys(EVENTS).forEach(event => {
      const eventKey = getEventKey(event);
      updates[eventKey] = true;
    });
    onChange(updates);
  };

  const disableAll = () => {
    const updates: any = {};
    Object.keys(EVENTS).forEach(event => {
      const eventKey = getEventKey(event);
      updates[eventKey] = false;
    });
    onChange(updates);
  };

  const filteredEvents = Object.entries(EVENTS).filter(([key, event]) => {
    if (categoryFilter !== 'all' && event.category !== categoryFilter) {
      return false;
    }
    if (severityFilter !== 'all' && event.severity !== severityFilter) {
      return false;
    }
    return true;
  });

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'info':
        return <Info className="h-4 w-4 text-blue-500" />;
      case 'warning':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'error':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return null;
    }
  };

  const getSeverityBadge = (severity: string) => {
    const variants: any = {
      info: 'default',
      warning: 'secondary',
      error: 'destructive',
    };
    return (
      <Badge variant={variants[severity] || 'default'} className="ml-2">
        {severity}
      </Badge>
    );
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Event Subscriptions</CardTitle>
          <CardDescription>
            Choose which events trigger notifications on each channel
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex gap-4">
              <div className="space-y-1">
                <Label>Category</Label>
                <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Categories</SelectItem>
                    {Object.entries(EVENT_CATEGORIES).map(([key, cat]) => (
                      <SelectItem key={key} value={key}>
                        <span className="mr-2">{cat.icon}</span>
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label>Severity</Label>
                <Select value={severityFilter} onValueChange={setSeverityFilter}>
                  <SelectTrigger className="w-[150px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Severities</SelectItem>
                    <SelectItem value="info">Info</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="error">Error</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={enableAll}>
                Enable All
              </Button>
              <Button variant="outline" size="sm" onClick={disableAll}>
                Disable All
              </Button>
            </div>
          </div>

          <div className="border rounded-lg overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[300px]">Event</TableHead>
                  {CHANNELS.map(channel => (
                    <TableHead key={channel.id} className="text-center">
                      <div className="flex items-center justify-center gap-1">
                        <span>{channel.icon}</span>
                        <span>{channel.label}</span>
                      </div>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredEvents.map(([eventKey, event]) => (
                  <TableRow key={eventKey}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        {getSeverityIcon(event.severity)}
                        <span className="font-medium">{event.label}</span>
                        {getSeverityBadge(event.severity)}
                      </div>
                    </TableCell>
                    {CHANNELS.map(channel => (
                      <TableCell key={channel.id} className="text-center">
                        <Checkbox
                          checked={isEventEnabled(eventKey, channel.id)}
                          onCheckedChange={(checked) => 
                            toggleEvent(eventKey, channel.id, checked as boolean)
                          }
                          disabled={
                            (channel.id === 'discord' && !settings.discord_enabled) ||
                            (channel.id === 'email' && !settings.email_enabled) ||
                            (channel.id === 'twitter' && !settings.twitter_enabled) ||
                            (channel.id === 'webhook' && !settings.webhook_enabled)
                          }
                        />
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="text-sm text-muted-foreground">
            <p>
              Note: Channels must be enabled in the Providers tab before you can subscribe to events.
              Disabled checkboxes indicate the channel is not configured.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}