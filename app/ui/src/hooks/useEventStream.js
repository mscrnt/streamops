import { useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

export function useEventStream() {
  const queryClient = useQueryClient();

  const handleEvent = useCallback((event) => {
    const data = JSON.parse(event.data);
    
    switch (event.type) {
      case 'asset.created':
        // New asset was created, invalidate recent assets
        console.log('New asset created:', data.filepath);
        queryClient.invalidateQueries(['assets', 'recent']);
        toast.success(`New recording: ${data.filepath.split('/').pop()}`);
        break;
        
      case 'recording.state':
        // Recording state changed - update guardrails immediately
        console.log('Recording state changed:', data.is_recording);
        
        // Immediately update system summary for guardrails status
        queryClient.invalidateQueries(['system', 'summary']);
        
        if (!data.is_recording) {
          // Recording stopped, assets will be indexed soon
          // The asset.created event will handle refreshing the assets list
          toast.info('Recording stopped, processing new files...');
        } else {
          // Recording started
          toast.info('Recording started');
        }
        break;
        
      case 'heartbeat':
        // Keep connection alive
        break;
        
      default:
        console.log('Unknown event:', event.type, data);
    }
  }, [queryClient]);

  useEffect(() => {
    let eventSource = null;
    let reconnectTimeout = null;

    const connect = () => {
      console.log('Connecting to event stream...');
      eventSource = new EventSource('/api/events/stream');

      eventSource.onopen = () => {
        console.log('Connected to event stream');
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        
        // Reconnect after 5 seconds
        reconnectTimeout = setTimeout(() => {
          connect();
        }, 5000);
      };

      // Listen for specific events
      eventSource.addEventListener('asset.created', handleEvent);
      eventSource.addEventListener('recording.state', handleEvent);
      eventSource.addEventListener('heartbeat', handleEvent);
      eventSource.addEventListener('connected', (event) => {
        console.log('Event stream connected:', event.data);
      });
    };

    connect();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [handleEvent]);
}