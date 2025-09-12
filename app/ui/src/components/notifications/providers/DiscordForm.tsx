import React, { useState } from 'react';
import { Label } from '@/components/ui/Label';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { useToast } from '@/components/ui/use-toast';
import { Eye, EyeOff, RotateCw, TestTube, Info } from 'lucide-react';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/Popover';

interface DiscordFormProps {
  settings: any;
  onChange: (updates: any) => void;
}

export default function DiscordForm({ settings, onChange }: DiscordFormProps) {
  const [showWebhook, setShowWebhook] = useState(false);
  const [testing, setTesting] = useState(false);
  const { toast } = useToast();

  const handleTest = async () => {
    if (!settings.discord_webhook_url) {
      toast({
        title: 'Error',
        description: 'Please enter a webhook URL first',
        variant: 'destructive',
      });
      return;
    }

    setTesting(true);
    try {
      const response = await fetch('/api/notifications/test/discord', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (result.ok) {
        toast({
          title: 'Test successful',
          description: `Message sent to Discord (${result.details?.latency_ms || 0}ms)`,
        });
      } else {
        toast({
          title: 'Test failed',
          description: result.message || 'Failed to send test message',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to test Discord webhook',
        variant: 'destructive',
      });
    } finally {
      setTesting(false);
    }
  };

  const handleRotateWebhook = () => {
    onChange({ discord_webhook_url: '' });
    setShowWebhook(false);
    toast({
      title: 'Webhook reset',
      description: 'Please enter a new Discord webhook URL',
    });
  };

  const validateWebhookUrl = (url: string) => {
    if (!url) return true;
    const pattern = /^https:\/\/discord(app)?\.com\/api\/webhooks\/\d+\/.+$/;
    return pattern.test(url);
  };

  const isValidUrl = validateWebhookUrl(settings.discord_webhook_url || '');

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="discord-enable" className="text-base font-medium">
            Enable Discord Notifications
          </Label>
          <p className="text-sm text-muted-foreground">
            Send notifications to a Discord channel via webhook
          </p>
        </div>
        <Switch
          id="discord-enable"
          checked={settings.discord_enabled || false}
          onCheckedChange={(checked) => onChange({ discord_enabled: checked })}
        />
      </div>

      {settings.discord_enabled && (
        <>
          <div className="space-y-2">
            <Label htmlFor="webhook-url">Webhook URL</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <Input
                  id="webhook-url"
                  type={showWebhook ? 'text' : 'password'}
                  placeholder="https://discord.com/api/webhooks/..."
                  value={settings.discord_webhook_url || ''}
                  onChange={(e) => onChange({ discord_webhook_url: e.target.value })}
                  className={!isValidUrl ? 'border-red-500' : ''}
                />
                {settings.discord_webhook_url && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => setShowWebhook(!showWebhook)}
                  >
                    {showWebhook ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              
              <Popover>
                <PopoverTrigger asChild>
                  <Button variant="outline" size="icon">
                    <RotateCw className="h-4 w-4" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-80">
                  <div className="space-y-2">
                    <p className="text-sm font-medium">Reset Webhook?</p>
                    <p className="text-sm text-muted-foreground">
                      This will clear the current webhook URL. You'll need to create a new webhook in Discord.
                    </p>
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleRotateWebhook}
                      className="w-full"
                    >
                      Reset Webhook
                    </Button>
                  </div>
                </PopoverContent>
              </Popover>
            </div>
            {!isValidUrl && settings.discord_webhook_url && (
              <p className="text-sm text-red-500">
                Invalid Discord webhook URL format
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="username">Bot Username (Optional)</Label>
            <Input
              id="username"
              placeholder="StreamOps"
              value={settings.discord_username || ''}
              onChange={(e) => onChange({ discord_username: e.target.value })}
            />
            <p className="text-sm text-muted-foreground">
              Override the default webhook username
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="avatar-url">Avatar URL (Optional)</Label>
            <Input
              id="avatar-url"
              placeholder="https://example.com/avatar.png"
              value={settings.discord_avatar_url || ''}
              onChange={(e) => onChange({ discord_avatar_url: e.target.value })}
            />
            <p className="text-sm text-muted-foreground">
              Custom avatar image for the bot
            </p>
          </div>

          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              To get a webhook URL:
              <ol className="mt-2 ml-4 list-decimal text-sm">
                <li>Open Discord and go to your server</li>
                <li>Right-click the channel → Edit Channel → Integrations</li>
                <li>Click "Create Webhook" or select existing</li>
                <li>Copy the webhook URL</li>
              </ol>
            </AlertDescription>
          </Alert>

          <div className="flex justify-end">
            <Button
              onClick={handleTest}
              disabled={testing || !settings.discord_webhook_url || !isValidUrl}
            >
              <TestTube className="h-4 w-4 mr-2" />
              {testing ? 'Testing...' : 'Send Test Message'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}