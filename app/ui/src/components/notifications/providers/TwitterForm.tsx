import React, { useState } from 'react';
import { Label } from '@/components/ui/Label';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { RadioGroup, RadioGroupItem } from '@/components/ui/RadioGroup';
import { useToast } from '@/components/ui/use-toast';
import { Eye, EyeOff, TestTube, Info } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/Alert';

interface TwitterFormProps {
  settings: any;
  onChange: (updates: any) => void;
}

export default function TwitterForm({ settings, onChange }: TwitterFormProps) {
  const [showSecrets, setShowSecrets] = useState({
    bearer: false,
    apiSecret: false,
    accessSecret: false,
  });
  const [testing, setTesting] = useState(false);
  const { toast } = useToast();

  const handleTest = async () => {
    setTesting(true);
    try {
      const response = await fetch('/api/notifications/test/twitter', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (result.ok) {
        toast({
          title: 'Test successful',
          description: `Tweet posted successfully (${result.details?.latency_ms || 0}ms)`,
        });
      } else {
        toast({
          title: 'Test failed',
          description: result.message || 'Failed to post test tweet',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to test Twitter configuration',
        variant: 'destructive',
      });
    } finally {
      setTesting(false);
    }
  };

  const canTest = () => {
    if (settings.twitter_auth_type === 'bearer') {
      return !!settings.twitter_bearer_token;
    } else {
      return !!(
        settings.twitter_api_key &&
        settings.twitter_api_secret &&
        settings.twitter_access_token &&
        settings.twitter_access_secret
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="twitter-enable" className="text-base font-medium">
            Enable Twitter/X Notifications
          </Label>
          <p className="text-sm text-muted-foreground">
            Post notifications to Twitter/X
          </p>
        </div>
        <Switch
          id="twitter-enable"
          checked={settings.twitter_enabled || false}
          onCheckedChange={(checked) => onChange({ twitter_enabled: checked })}
        />
      </div>

      {settings.twitter_enabled && (
        <>
          <div className="space-y-2">
            <Label>Authentication Type</Label>
            <RadioGroup
              value={settings.twitter_auth_type || 'bearer'}
              onValueChange={(value) => onChange({ twitter_auth_type: value })}
            >
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="bearer" id="bearer" />
                <Label htmlFor="bearer">Bearer Token (Read + Write)</Label>
              </div>
              <div className="flex items-center space-x-2">
                <RadioGroupItem value="oauth1" id="oauth1" />
                <Label htmlFor="oauth1">OAuth 1.0a (API Keys + Access Tokens)</Label>
              </div>
            </RadioGroup>
          </div>

          {settings.twitter_auth_type === 'bearer' ? (
            <div className="space-y-2">
              <Label htmlFor="bearer-token">Bearer Token</Label>
              <div className="relative">
                <Input
                  id="bearer-token"
                  type={showSecrets.bearer ? 'text' : 'password'}
                  placeholder="Enter your Twitter Bearer Token"
                  value={settings.twitter_bearer_token || ''}
                  onChange={(e) => onChange({ twitter_bearer_token: e.target.value })}
                />
                {settings.twitter_bearer_token && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => setShowSecrets({ ...showSecrets, bearer: !showSecrets.bearer })}
                  >
                    {showSecrets.bearer ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
            </div>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="api-key">API Key</Label>
                  <Input
                    id="api-key"
                    placeholder="Your API Key"
                    value={settings.twitter_api_key || ''}
                    onChange={(e) => onChange({ twitter_api_key: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="api-secret">API Secret</Label>
                  <div className="relative">
                    <Input
                      id="api-secret"
                      type={showSecrets.apiSecret ? 'text' : 'password'}
                      placeholder="Your API Secret"
                      value={settings.twitter_api_secret || ''}
                      onChange={(e) => onChange({ twitter_api_secret: e.target.value })}
                    />
                    {settings.twitter_api_secret && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                        onClick={() => setShowSecrets({ ...showSecrets, apiSecret: !showSecrets.apiSecret })}
                      >
                        {showSecrets.apiSecret ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="access-token">Access Token</Label>
                  <Input
                    id="access-token"
                    placeholder="Your Access Token"
                    value={settings.twitter_access_token || ''}
                    onChange={(e) => onChange({ twitter_access_token: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="access-secret">Access Token Secret</Label>
                  <div className="relative">
                    <Input
                      id="access-secret"
                      type={showSecrets.accessSecret ? 'text' : 'password'}
                      placeholder="Your Access Token Secret"
                      value={settings.twitter_access_secret || ''}
                      onChange={(e) => onChange({ twitter_access_secret: e.target.value })}
                    />
                    {settings.twitter_access_secret && (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                        onClick={() => setShowSecrets({ ...showSecrets, accessSecret: !showSecrets.accessSecret })}
                      >
                        {showSecrets.accessSecret ? (
                          <EyeOff className="h-4 w-4" />
                        ) : (
                          <Eye className="h-4 w-4" />
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}

          <Alert>
            <Info className="h-4 w-4" />
            <AlertDescription>
              {settings.twitter_auth_type === 'bearer' ? (
                <>
                  To get a Bearer Token:
                  <ol className="mt-2 ml-4 list-decimal text-sm">
                    <li>Go to developer.twitter.com</li>
                    <li>Create or select your app</li>
                    <li>Go to "Keys and tokens"</li>
                    <li>Generate a Bearer Token with Read + Write permissions</li>
                  </ol>
                </>
              ) : (
                <>
                  To get OAuth 1.0a credentials:
                  <ol className="mt-2 ml-4 list-decimal text-sm">
                    <li>Go to developer.twitter.com</li>
                    <li>Create or select your app</li>
                    <li>Go to "Keys and tokens"</li>
                    <li>Copy API Key and Secret</li>
                    <li>Generate Access Token and Secret</li>
                  </ol>
                </>
              )}
            </AlertDescription>
          </Alert>

          <div className="flex justify-end">
            <Button
              onClick={handleTest}
              disabled={testing || !canTest()}
            >
              <TestTube className="h-4 w-4 mr-2" />
              {testing ? 'Testing...' : 'Send Test Tweet'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}