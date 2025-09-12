import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/Card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import DiscordForm from './providers/DiscordForm';
import EmailForm from './providers/EmailForm';
import TwitterForm from './providers/TwitterForm';
import WebhooksForm from './providers/WebhooksForm';
import { MessageSquare, Mail, Twitter, Webhook } from 'lucide-react';

interface ProvidersTabProps {
  settings: any;
  onChange: (updates: any) => void;
}

export default function ProvidersTab({ settings, onChange }: ProvidersTabProps) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Notification Providers</CardTitle>
          <CardDescription>
            Configure external services to receive notifications about StreamOps events.
            Your credentials are encrypted and never exposed in API responses.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="discord" className="space-y-4">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="discord" className="flex items-center gap-2">
                <MessageSquare className="h-4 w-4" />
                Discord
              </TabsTrigger>
              <TabsTrigger value="email" className="flex items-center gap-2">
                <Mail className="h-4 w-4" />
                Email
              </TabsTrigger>
              <TabsTrigger value="twitter" className="flex items-center gap-2">
                <Twitter className="h-4 w-4" />
                Twitter/X
              </TabsTrigger>
              <TabsTrigger value="webhooks" className="flex items-center gap-2">
                <Webhook className="h-4 w-4" />
                Webhooks
              </TabsTrigger>
            </TabsList>

            <TabsContent value="discord">
              <DiscordForm
                settings={settings || {}}
                onChange={onChange}
              />
            </TabsContent>

            <TabsContent value="email">
              <EmailForm
                settings={settings || {}}
                onChange={onChange}
              />
            </TabsContent>

            <TabsContent value="twitter">
              <TwitterForm
                settings={settings || {}}
                onChange={onChange}
              />
            </TabsContent>

            <TabsContent value="webhooks">
              <WebhooksForm
                settings={settings || {}}
                onChange={onChange}
              />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  );
}