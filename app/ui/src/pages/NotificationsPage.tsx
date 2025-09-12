import React, { useState, useEffect } from 'react';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Alert, AlertDescription } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/use-toast';
import { Bell, Save, AlertCircle } from 'lucide-react';
import ProvidersTab from '@/components/notifications/ProvidersTab';
import EventsTab from '@/components/notifications/EventsTab';
import TemplatesTab from '@/components/notifications/TemplatesTab';
import AuditTab from '@/components/notifications/AuditTab';

export default function NotificationsPage() {
  const [activeTab, setActiveTab] = useState('providers');
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      const response = await fetch('/api/settings');
      if (!response.ok) throw new Error('Failed to load settings');
      const data = await response.json();
      setSettings(data.notifications || {});
    } catch (error) {
      console.error('Failed to load notification settings:', error);
      toast({
        title: 'Error',
        description: 'Failed to load notification settings',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      console.log('Saving notification settings:', settings);
      
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notifications: settings }),
      });
      
      if (!response.ok) {
        const errorData = await response.text();
        console.error('Save failed:', errorData);
        throw new Error('Failed to save settings');
      }
      
      const data = await response.json();
      console.log('Server response:', data);
      
      // Don't overwrite local settings with redacted response
      // Only update if we don't have sensitive fields that were redacted
      const updatedSettings = { ...settings };
      if (data.notifications) {
        // Preserve password fields if they were redacted
        if (data.notifications.email_smtp_pass === '********') {
          data.notifications.email_smtp_pass = settings.email_smtp_pass;
        }
        if (data.notifications.discord_webhook_url && data.notifications.discord_webhook_url.includes('********')) {
          data.notifications.discord_webhook_url = settings.discord_webhook_url;
        }
        if (data.notifications.twitter_bearer_token === '********') {
          data.notifications.twitter_bearer_token = settings.twitter_bearer_token;
        }
        if (data.notifications.twitter_api_secret === '********') {
          data.notifications.twitter_api_secret = settings.twitter_api_secret;
        }
        if (data.notifications.twitter_access_secret === '********') {
          data.notifications.twitter_access_secret = settings.twitter_access_secret;
        }
        setSettings(data.notifications);
      }
      
      setHasUnsavedChanges(false);
      
      toast({
        title: 'Settings saved',
        description: 'Notification settings have been updated successfully',
      });
    } catch (error) {
      console.error('Failed to save settings:', error);
      toast({
        title: 'Error',
        description: 'Failed to save notification settings',
        variant: 'destructive',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleSettingsChange = (updates) => {
    setSettings((prev) => ({ ...prev, ...updates }));
    setHasUnsavedChanges(true);
  };

  const handleDiscard = () => {
    loadSettings();
    setHasUnsavedChanges(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-6 max-w-7xl">
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Bell className="h-8 w-8 text-primary" />
            <div>
              <h1 className="text-3xl font-bold">Notifications</h1>
              <p className="text-muted-foreground">
                Configure notification channels and event subscriptions
              </p>
            </div>
          </div>
          
          {hasUnsavedChanges && (
            <div className="flex items-center gap-2">
              <Alert className="py-2 px-4 border-orange-500 bg-orange-50 dark:bg-orange-950">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>You have unsaved changes</AlertDescription>
              </Alert>
              <Button variant="outline" onClick={handleDiscard}>
                Discard
              </Button>
              <Button onClick={saveSettings} disabled={saving}>
                <Save className="h-4 w-4 mr-2" />
                {saving ? 'Saving...' : 'Save Changes'}
              </Button>
            </div>
          )}
        </div>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-4">
        <TabsList className="grid w-full grid-cols-4">
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="events">Events</TabsTrigger>
          <TabsTrigger value="templates">Templates</TabsTrigger>
          <TabsTrigger value="audit">Audit</TabsTrigger>
        </TabsList>

        <TabsContent value="providers" className="space-y-4">
          <ProvidersTab 
            settings={settings} 
            onChange={handleSettingsChange}
          />
        </TabsContent>

        <TabsContent value="events" className="space-y-4">
          <EventsTab 
            settings={settings} 
            onChange={handleSettingsChange}
          />
        </TabsContent>

        <TabsContent value="templates" className="space-y-4">
          <TemplatesTab />
        </TabsContent>

        <TabsContent value="audit" className="space-y-4">
          <AuditTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}