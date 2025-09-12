import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Label } from '@/components/ui/Label';
import { Input } from '@/components/ui/Input';
import { Textarea } from '@/components/ui/Textarea';
import { Badge } from '@/components/ui/Badge';
import { useToast } from '@/components/ui/use-toast';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/Dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/Select';
import { Plus, Edit, Trash2, Eye, Copy } from 'lucide-react';
import { format } from 'date-fns';

interface Template {
  id: string;
  name: string;
  channel: string;
  subject?: string;
  body: string;
  is_default?: boolean;
  updated_at: string;
}

export default function TemplatesTab() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingTemplate, setEditingTemplate] = useState<Template | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<Template | null>(null);
  const [previewPayload, setPreviewPayload] = useState('{}');
  const [previewResult, setPreviewResult] = useState<any>(null);
  const { toast } = useToast();

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
      toast({
        title: 'Error',
        description: 'Failed to load notification templates',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const saveTemplate = async () => {
    if (!editingTemplate) return;

    try {
      const method = editingTemplate.id ? 'PUT' : 'POST';
      const url = editingTemplate.id 
        ? `/api/notifications/templates/${editingTemplate.id}`
        : '/api/notifications/templates';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(editingTemplate),
      });

      if (response.ok) {
        toast({
          title: 'Template saved',
          description: 'Notification template has been saved successfully',
        });
        await loadTemplates();
        setShowEditor(false);
        setEditingTemplate(null);
      } else {
        throw new Error('Failed to save template');
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to save template',
        variant: 'destructive',
      });
    }
  };

  const deleteTemplate = async (id: string) => {
    try {
      const response = await fetch(`/api/notifications/templates/${id}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        toast({
          title: 'Template deleted',
          description: 'Notification template has been deleted',
        });
        await loadTemplates();
      } else {
        throw new Error('Failed to delete template');
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to delete template',
        variant: 'destructive',
      });
    }
  };

  const duplicateTemplate = (template: Template) => {
    setEditingTemplate({
      ...template,
      id: '',
      name: `${template.name} (Copy)`,
      is_default: false,
    });
    setShowEditor(true);
  };

  const previewTemplateRender = async () => {
    if (!previewTemplate) return;

    try {
      const payload = JSON.parse(previewPayload);
      
      const response = await fetch('/api/notifications/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          channel: previewTemplate.channel,
          template_id: previewTemplate.id,
          payload,
        }),
      });

      if (response.ok) {
        const result = await response.json();
        setPreviewResult(result);
      } else {
        throw new Error('Failed to preview template');
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: error instanceof SyntaxError 
          ? 'Invalid JSON payload' 
          : 'Failed to preview template',
        variant: 'destructive',
      });
    }
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

  const getDefaultPayload = () => {
    return JSON.stringify({
      event_type: 'job.completed',
      job_type: 'remux',
      asset_name: 'recording_2025_01_15.mp4',
      output_path: '/data/processed/recording_2025_01_15.mov',
      duration_sec: 3600,
      scene: 'Gaming',
      profile: 'High Quality',
    }, null, 2);
  };

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Notification Templates</CardTitle>
              <CardDescription>
                Create and manage reusable notification templates for different channels
              </CardDescription>
            </div>
            <Button onClick={() => {
              setEditingTemplate({
                id: '',
                name: '',
                channel: 'discord',
                body: '',
                updated_at: new Date().toISOString(),
              });
              setShowEditor(true);
            }}>
              <Plus className="h-4 w-4 mr-2" />
              New Template
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-32">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            </div>
          ) : templates.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              No templates created yet. Click "New Template" to get started.
            </div>
          ) : (
            <div className="grid gap-4">
              {templates.map((template) => (
                <Card key={template.id}>
                  <CardContent className="pt-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xl">{getChannelIcon(template.channel)}</span>
                          <h3 className="font-semibold">{template.name}</h3>
                          {template.is_default && (
                            <Badge variant="secondary">Default</Badge>
                          )}
                          <Badge variant="outline">{template.channel}</Badge>
                        </div>
                        {template.subject && (
                          <p className="text-sm text-muted-foreground mb-1">
                            Subject: {template.subject}
                          </p>
                        )}
                        <p className="text-sm text-muted-foreground line-clamp-2">
                          {template.body}
                        </p>
                        <p className="text-xs text-muted-foreground mt-2">
                          Updated {format(new Date(template.updated_at), 'PPp')}
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setPreviewTemplate(template);
                            setPreviewPayload(getDefaultPayload());
                            setPreviewResult(null);
                            setShowPreview(true);
                          }}
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => duplicateTemplate(template)}
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => {
                            setEditingTemplate(template);
                            setShowEditor(true);
                          }}
                        >
                          <Edit className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => deleteTemplate(template.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Template Editor Dialog */}
      <Dialog open={showEditor} onOpenChange={setShowEditor}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {editingTemplate?.id ? 'Edit Template' : 'Create Template'}
            </DialogTitle>
            <DialogDescription>
              Create a reusable notification template with variables
            </DialogDescription>
          </DialogHeader>
          
          {editingTemplate && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={editingTemplate.name}
                    onChange={(e) => setEditingTemplate({
                      ...editingTemplate,
                      name: e.target.value,
                    })}
                    placeholder="Template name"
                  />
                </div>
                
                <div className="space-y-2">
                  <Label>Channel</Label>
                  <Select
                    value={editingTemplate.channel}
                    onValueChange={(value) => setEditingTemplate({
                      ...editingTemplate,
                      channel: value,
                    })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="discord">Discord</SelectItem>
                      <SelectItem value="email">Email</SelectItem>
                      <SelectItem value="twitter">Twitter/X</SelectItem>
                      <SelectItem value="webhook">Webhook</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {editingTemplate.channel === 'email' && (
                <div className="space-y-2">
                  <Label>Subject</Label>
                  <Input
                    value={editingTemplate.subject || ''}
                    onChange={(e) => setEditingTemplate({
                      ...editingTemplate,
                      subject: e.target.value,
                    })}
                    placeholder="Email subject line"
                  />
                </div>
              )}

              <div className="space-y-2">
                <Label>Body</Label>
                <Textarea
                  value={editingTemplate.body}
                  onChange={(e) => setEditingTemplate({
                    ...editingTemplate,
                    body: e.target.value,
                  })}
                  placeholder="Template body with {variables}"
                  className="min-h-[200px] font-mono"
                />
                <p className="text-sm text-muted-foreground">
                  Use {'{variable}'} syntax for dynamic content. Common variables:
                  {'{event_type}'}, {'{asset_name}'}, {'{job_type}'}, {'{duration_sec}'}
                </p>
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowEditor(false)}>
              Cancel
            </Button>
            <Button onClick={saveTemplate}>
              Save Template
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Template Preview Dialog */}
      <Dialog open={showPreview} onOpenChange={setShowPreview}>
        <DialogContent className="max-w-3xl">
          <DialogHeader>
            <DialogTitle>Preview Template</DialogTitle>
            <DialogDescription>
              Test how your template renders with sample data
            </DialogDescription>
          </DialogHeader>
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Test Payload (JSON)</Label>
              <Textarea
                value={previewPayload}
                onChange={(e) => setPreviewPayload(e.target.value)}
                className="min-h-[300px] font-mono text-sm"
              />
            </div>
            
            <div className="space-y-2">
              <Label>Rendered Output</Label>
              <div className="border rounded-lg p-4 min-h-[300px] bg-muted/50">
                {previewResult ? (
                  <div className="space-y-2">
                    {previewResult.subject && (
                      <div>
                        <Label className="text-xs">Subject:</Label>
                        <p className="font-medium">{previewResult.subject}</p>
                      </div>
                    )}
                    <div>
                      <Label className="text-xs">Body:</Label>
                      <p className="whitespace-pre-wrap">{previewResult.body}</p>
                    </div>
                    {previewResult.truncated && (
                      <Badge variant="secondary">
                        Truncated for {previewTemplate?.channel}
                      </Badge>
                    )}
                  </div>
                ) : (
                  <p className="text-muted-foreground">
                    Click "Preview" to see the rendered template
                  </p>
                )}
              </div>
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowPreview(false)}>
              Close
            </Button>
            <Button onClick={previewTemplateRender}>
              Preview
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}