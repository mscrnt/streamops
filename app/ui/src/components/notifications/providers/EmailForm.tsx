import React, { useState } from 'react';
import { Label } from '@/components/ui/Label';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/use-toast';
import { Eye, EyeOff, TestTube, X, Plus, Mail } from 'lucide-react';
import { Badge } from '@/components/ui/Badge';
import { Alert } from '@/components/ui/Alert';

interface EmailFormProps {
  settings: any;
  onChange: (updates: any) => void;
}

export default function EmailForm({ settings, onChange }: EmailFormProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [testing, setTesting] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [localPassword, setLocalPassword] = useState('');
  const [passwordModified, setPasswordModified] = useState(false);
  const { toast } = useToast();
  
  // Initialize local password when settings change (but not if it's censored)
  React.useEffect(() => {
    if (settings.email_smtp_pass && settings.email_smtp_pass !== '********' && !passwordModified) {
      setLocalPassword(settings.email_smtp_pass);
    }
  }, [settings.email_smtp_pass]);

  const applyGooglePreset = () => {
    onChange({
      email_smtp_host: 'smtp.gmail.com',
      email_smtp_port: 587,
      email_use_tls: true,
      email_use_ssl: false,
    });
    toast({
      title: 'Google settings applied',
      description: 'Use your Gmail address and an App Password for authentication',
    });
  };

  const applyOutlookPreset = () => {
    onChange({
      email_smtp_host: 'smtp-mail.outlook.com',
      email_smtp_port: 587,
      email_use_tls: true,
      email_use_ssl: false,
    });
    toast({
      title: 'Outlook settings applied',
      description: 'Use your Outlook email and password for authentication',
    });
  };

  const handleTest = async () => {
    if (!settings.email_smtp_host || !settings.email_from) {
      toast({
        title: 'Error',
        description: 'Please configure SMTP settings first',
        variant: 'destructive',
      });
      return;
    }

    if (!settings.email_to || settings.email_to.length === 0) {
      toast({
        title: 'Error',
        description: 'Please add at least one recipient email address',
        variant: 'destructive',
      });
      return;
    }

    if (!settings.email_smtp_user || !settings.email_smtp_pass) {
      toast({
        title: 'Error',
        description: 'Please provide SMTP username and password',
        variant: 'destructive',
      });
      return;
    }

    setTesting(true);
    try {
      const response = await fetch('/api/notifications/test/email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      const result = await response.json();
      
      if (result.ok) {
        toast({
          title: 'Test successful',
          description: `Email sent successfully to ${settings.email_to.join(', ')}`,
        });
      } else {
        toast({
          title: 'Test failed',
          description: result.message || 'Failed to send test email',
          variant: 'destructive',
        });
      }
    } catch (error) {
      toast({
        title: 'Error',
        description: 'Failed to test email configuration',
        variant: 'destructive',
      });
    } finally {
      setTesting(false);
    }
  };

  const addRecipient = () => {
    if (!newEmail) return;
    
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(newEmail)) {
      toast({
        title: 'Invalid email',
        description: 'Please enter a valid email address',
        variant: 'destructive',
      });
      return;
    }

    const currentEmails = settings.email_to || [];
    if (currentEmails.includes(newEmail)) {
      toast({
        title: 'Duplicate email',
        description: 'This email is already in the recipient list',
        variant: 'destructive',
      });
      return;
    }

    onChange({ email_to: [...currentEmails, newEmail] });
    setNewEmail('');
  };

  const removeRecipient = (email: string) => {
    const currentEmails = settings.email_to || [];
    onChange({ email_to: currentEmails.filter((e: string) => e !== email) });
  };

  const validatePort = (port: string) => {
    const portNum = parseInt(port);
    return portNum > 0 && portNum <= 65535;
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="space-y-0.5">
          <Label htmlFor="email-enable" className="text-base font-medium">
            Enable Email Notifications
          </Label>
          <p className="text-sm text-muted-foreground">
            Send notifications via SMTP email server
          </p>
        </div>
        <Switch
          id="email-enable"
          checked={settings.email_enabled || false}
          onCheckedChange={(checked) => onChange({ email_enabled: checked })}
        />
      </div>

      {settings.email_enabled && (
        <>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={applyGooglePreset}
            >
              <Mail className="h-4 w-4 mr-2" />
              Use Gmail Settings
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={applyOutlookPreset}
            >
              <Mail className="h-4 w-4 mr-2" />
              Use Outlook Settings
            </Button>
          </div>

          {settings.email_smtp_host === 'smtp.gmail.com' && (
            <Alert>
              <div className="space-y-2">
                <p className="font-medium">Gmail Configuration:</p>
                <ol className="text-sm space-y-1 ml-4">
                  <li>1. Enable 2-factor authentication in your Google account</li>
                  <li>2. Generate an App Password at: <code>myaccount.google.com/apppasswords</code></li>
                  <li>3. Use your Gmail address as both username and from email</li>
                  <li>4. Use the App Password (not your regular password)</li>
                </ol>
              </div>
            </Alert>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="smtp-host">SMTP Host</Label>
              <Input
                id="smtp-host"
                placeholder="smtp.gmail.com"
                value={settings.email_smtp_host || ''}
                onChange={(e) => onChange({ email_smtp_host: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp-port">SMTP Port</Label>
              <Input
                id="smtp-port"
                type="number"
                placeholder="587"
                value={settings.email_smtp_port || 587}
                onChange={(e) => {
                  const port = parseInt(e.target.value);
                  if (!isNaN(port)) {
                    onChange({ email_smtp_port: port });
                  }
                }}
                className={!validatePort(settings.email_smtp_port?.toString() || '587') ? 'border-red-500' : ''}
              />
              {!validatePort(settings.email_smtp_port?.toString() || '587') && (
                <p className="text-sm text-red-500">Invalid port (1-65535)</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="smtp-user">SMTP Username</Label>
              <Input
                id="smtp-user"
                placeholder="user@gmail.com"
                value={settings.email_smtp_user || ''}
                onChange={(e) => onChange({ email_smtp_user: e.target.value })}
              />
              {settings.email_smtp_host === 'smtp.gmail.com' && (
                <p className="text-xs text-muted-foreground">Use your full Gmail address</p>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="smtp-pass">SMTP Password / App Password</Label>
              <div className="relative">
                <Input
                  id="smtp-pass"
                  type={showPassword ? 'text' : 'password'}
                  placeholder={settings.email_smtp_pass === '********' ? 'Password is saved (enter new to change)' : '••••••••'}
                  value={passwordModified ? localPassword : (settings.email_smtp_pass === '********' ? '' : settings.email_smtp_pass || '')}
                  onChange={(e) => {
                    setLocalPassword(e.target.value);
                    setPasswordModified(true);
                    onChange({ email_smtp_pass: e.target.value });
                  }}
                />
                {(passwordModified && localPassword) && (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="absolute right-2 top-1/2 -translate-y-1/2 h-7 w-7 p-0"
                    onClick={() => setShowPassword(!showPassword)}
                  >
                    {showPassword ? (
                      <EyeOff className="h-4 w-4" />
                    ) : (
                      <Eye className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
              {settings.email_smtp_pass === '********' && !passwordModified && (
                <p className="text-xs text-green-600 dark:text-green-400">
                  ✓ Password is securely saved. Enter a new password to change it.
                </p>
              )}
              {settings.email_smtp_host === 'smtp.gmail.com' && passwordModified && (
                <p className="text-xs text-muted-foreground">
                  Paste your App Password exactly as Google provides it (spaces are OK)
                </p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="from-email">From Email</Label>
            <Input
              id="from-email"
              type="email"
              placeholder="notifications@example.com"
              value={settings.email_from || ''}
              onChange={(e) => onChange({ email_from: e.target.value })}
            />
            {settings.email_smtp_host === 'smtp.gmail.com' && (
              <p className="text-xs text-muted-foreground">Should match your Gmail address</p>
            )}
          </div>

          <div className="space-y-2">
            <Label>Recipients</Label>
            <div className="flex gap-2">
              <Input
                placeholder="Add recipient email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && addRecipient()}
              />
              <Button onClick={addRecipient} size="icon">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            {settings.email_to && settings.email_to.length > 0 ? (
              <div className="flex flex-wrap gap-2 mt-2">
                {settings.email_to.map((email: string) => (
                  <Badge key={email} variant="secondary" className="pl-3 pr-1">
                    {email}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-4 w-4 p-0 ml-2"
                      onClick={() => removeRecipient(email)}
                    >
                      <X className="h-3 w-3" />
                    </Button>
                  </Badge>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground mt-2">No recipients added yet</p>
            )}
          </div>

          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Switch
                id="use-tls"
                checked={settings.email_use_tls !== false}
                onCheckedChange={(checked) => onChange({ 
                  email_use_tls: checked,
                  email_use_ssl: checked ? false : settings.email_use_ssl 
                })}
              />
              <Label htmlFor="use-tls">Use TLS (Port 587)</Label>
            </div>

            <div className="flex items-center gap-2">
              <Switch
                id="use-ssl"
                checked={settings.email_use_ssl || false}
                onCheckedChange={(checked) => onChange({ 
                  email_use_ssl: checked,
                  email_use_tls: checked ? false : settings.email_use_tls
                })}
              />
              <Label htmlFor="use-ssl">Use SSL (Port 465)</Label>
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button
              onClick={handleTest}
              disabled={testing || !settings.email_smtp_host || !settings.email_from || !settings.email_smtp_user || !settings.email_smtp_pass || !settings.email_to || settings.email_to.length === 0}
            >
              <TestTube className="h-4 w-4 mr-2" />
              {testing ? 'Testing...' : 'Send Test Email'}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}