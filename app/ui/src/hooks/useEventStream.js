import { useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';

export function useEventStream() {
  const queryClient = useQueryClient();

  const handleEvent = useCallback((event) => {
    const data = JSON.parse(event.data);
    
    switch (event.type) {
      case 'asset.created':
        // New asset was created, invalidate all assets queries
        console.log('New asset created:', data.filepath);
        queryClient.invalidateQueries(['assets']);
        toast.success(`New recording: ${data.filepath.split('/').pop()}`);
        break;
        
      case 'recording.state':
        // Recording state changed - update guardrails immediately
        console.log('Recording state changed:', data.is_recording);
        
        // Immediately update system summary for guardrails status
        queryClient.invalidateQueries(['system', 'summary']);
        
        if (!data.is_recording) {
          // Recording stopped, assets will be indexed soon
          // Also invalidate assets since new recordings might appear
          toast.success('Recording stopped, processing new files...');
          // Trigger asset refresh after a short delay to allow indexing
          setTimeout(() => {
            queryClient.invalidateQueries(['assets']);
          }, 2000);
        } else {
          // Recording started
          toast.success('Recording started');
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
    let reconnectAttempts = 0;
    const maxReconnectAttempts = 10;

    const connect = () => {
      console.log(`Connecting to event stream... (attempt ${reconnectAttempts + 1})`);
      
      // Clear any existing connection
      if (eventSource) {
        eventSource.close();
      }
      
      eventSource = new EventSource('/api/events/stream');

      eventSource.onopen = () => {
        console.log('Connected to event stream');
        reconnectAttempts = 0; // Reset attempts on successful connection
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        
        // Don't reconnect if we're cleaning up
        if (eventSource.readyState === EventSource.CLOSED) {
          return;
        }
        
        eventSource.close();
        
        // Exponential backoff for reconnection
        if (reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++;
          const delay = Math.min(5000 * Math.pow(1.5, reconnectAttempts - 1), 30000);
          console.log(`Reconnecting in ${delay}ms...`);
          reconnectTimeout = setTimeout(() => {
            connect();
          }, delay);
        } else {
          console.error('Max reconnection attempts reached');
        }
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