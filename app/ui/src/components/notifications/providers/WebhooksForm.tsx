import React, { useState } from 'react';
import { Label } from '@/components/ui/Label';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { Card, CardContent } from '@/components/ui/Card';
import { useToast } from '@/components/ui/use-toast';
import { Eye, EyeOff, TestTube, Plus, Trash2, Shield } from 'lucide-react';
import { v4 as uuidv4 } from 'uuid';

interface Webhook {
  id: string;
  name: string;
  url: string;
  secret?: string;
  active: boolean;
}

interface WebhooksFormProps {
  settings: any;
  onChange: (updates: any) => void;
}

export default function WebhooksForm({ settings, onChange }: WebhooksFormProps) {
  const [showSecrets, setShowSecrets] = useState<{ [key: string]: boolean }>({});
  const [testing, setTesting] = useState<string | null>(null);
  const { toast } = useToast();

  const webhooks: Webhook[] = settings.endpoints || [];

  const addWebhook = () => {
    const newWebhook: Webhook = {
      id: uuidv4(),
      name: `Webhook ${webhooks.length + 1}`,
      url: '',
      secret: '',
      active: true,
    };
    onChange({ 
      webhook_enabled: true,
      endpoints: [...webhooks, newWebhook] 
    });
  };

  const updateWebhook = (id: string, updates: Partial<Webhook>) => {
    const updated = webhooks.map(w => 
      w.id === id ? { ...w, ...updates } : w
    );
    onChange({ endpoints: updated });
  };

  const removeWebhook = (id: string) => {
    const filtered = webhooks.filter(w => w.id !== id);
    onChange({ 
      endpoints: filtered,
      webhook_enabled: filtered.length > 0 
    });
  };

  const testWebhook = async (webhook: Webhook) => {
    if (!webhook.url) {
      toast({
        title: 'Error',
        description: 'Please enter a webhook URL first',
        variant: 'destructive',
      });
      return;
    }

    setTesting(webhook.id);
    try {
      const response = await fetch('/api/notifications/test/webhook', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ webhook_id: webhook.id }),
      });
      
      const result = await response.json();
      
      if (result.ok) {
        toast({
          title: 'Test successful',
          description: `Webhook called successfully (${result.details?.latency_ms || 0}ms)`,
        });
      } else {
        toast({
          title: 'Test failed',
          description: result.message || 'Failed to call webhook',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to test webhook',
        variant: 'destructive',
      });
    } finally {
      setTesting(null);
    }
  };

  const testAllWebhooks = async () => {
    const activeWebhooks = webhooks.filter(w => w.active && w.url);
    if (activeWebhooks.length === 0) {
      toast({
        title: 'No active webhooks',
        description: 'Please configure at least one active webhook',
        variant: 'destructive',
      });
      return;
    }

    for (const webhook of activeWebhooks) {
      await testWebhook(webhook);
    }
  };

  const validateUrl = (url: string) => {
    if (!url) return true;
    try {
      new URL(url);
      return true;
    } catch {
      return false;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label className="text-base font-medium">
            Enable Webhook Notifications
          </Label>
          <p className="text-sm text-muted-foreground">
            Send notifications to custom webhook endpoints
          </p>
        </div>
        <Switch
          checked={settings.webhook_enabled || false}
          onCheckedChange={(checked) => onChange({ webhook_enabled: checked })}
        />
      </div>

      {settings.webhook_enabled && (
        <>
          <div className="space-y-4">
            {webhooks.map((webhook) => (
              <Card key={webhook.id}>
                <CardContent className="pt-6 space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex-1 grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Name</Label>
                        <Input
                          placeholder="Webhook name"
                          value={webhook.name}
                          onChange={(e) => updateWebhook(webhook.id, { name: e.target.value })}
                        />
                      </div>
                      
                      <div className="flex items-end gap-2">
                        <div className="flex items-center gap-2">
                          <Switch
                            checked={webhook.active}
                            onCheckedChange={(checked) => updateWebhook(webhook.id, { active: checked })}
                          />
                          <Label>Active</Label>
                        </div>
                        
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => removeWebhook(webhook.id)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label>URL</Label>
                    <Input
                      placeholder="https://example.com/webhook"
                      value={webhook.url}
                      onChange={(e) => updateWebhook(webhook.id, { url: e.target.value })}
                      className={!validateUrl(webhook.url) ? 'border-red-500' : ''}
                    />
                    {!validateUrl(webhook.url) && webhook.url && (
                      <p className="text-sm text-red-500">Invalid URL format</p>
                    )}
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <Shield className="h-4 w-4" />
                      <Label>Secret (for HMAC signing)</Label>
                    </div>
                    <div className="relative">
                      <Input
                        type={showSecrets[webhook.id] ? 'text' : 'password'}
                        placeholder="Optional secret for request signing"
                        value={webhook.secret || ''}
                        onChange={(e) => updateWebhook(webhook.id, { secret: e.target.value })}
                      />
                      {webhook.secret && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                          onClick={() => setShowSecrets({ 
                            ...showSecrets, 
                            [webhook.id]: !showSecrets[webhook.id] 
                          })}
                        >
                          {showSecrets[webhook.id] ? (
                            <EyeOff className="h-4 w-4" />
                          ) : (
                            <Eye className="h-4 w-4" />
                          )}
                        </Button>
                      )}
                    </div>
                    <p className="text-sm text-muted-foreground">
                      If provided, requests will include X-Signature header with HMAC-SHA256 signature
                    </p>
                  </div>

                  <div className="flex justify-end">
                    <Button
                      variant="outline"
                      onClick={() => testWebhook(webhook)}
                      disabled={testing === webhook.id || !webhook.url || !validateUrl(webhook.url)}
                    >
                      <TestTube className="h-4 w-4 mr-2" />
                      {testing === webhook.id ? 'Testing...' : 'Test'}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="flex justify-between">
            <Button onClick={addWebhook} variant="outline">
              <Plus className="h-4 w-4 mr-2" />
              Add Webhook
            </Button>
            
            {webhooks.length > 0 && (
              <Button
                onClick={testAllWebhooks}
                disabled={testing !== null}
              >
                <TestTube className="h-4 w-4 mr-2" />
                Test All Active
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}