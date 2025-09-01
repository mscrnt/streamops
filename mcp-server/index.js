#!/usr/bin/env node

/**
 * MCP Server for StreamOps API
 * Provides a consistent interface for interacting with the StreamOps API
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import axios from 'axios';

const API_BASE_URL = process.env.STREAMOPS_API_URL || 'http://localhost:7767/api';

// Create axios instance with defaults
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Helper to format API errors
function formatError(error) {
  if (error.response) {
    return `API Error ${error.response.status}: ${JSON.stringify(error.response.data)}`;
  } else if (error.request) {
    return `No response from API: ${error.message}`;
  } else {
    return `Request Error: ${error.message}`;
  }
}

// Create MCP server
const server = new Server(
  {
    name: 'streamops-api',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Define available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'streamops_list_assets',
      description: 'List assets with filtering and pagination',
      inputSchema: {
        type: 'object',
        properties: {
          page: { type: 'number', description: 'Page number (default: 1)' },
          per_page: { type: 'number', description: 'Items per page (default: 50, max: 100)' },
          status: { 
            type: 'string', 
            enum: ['active', 'archived', 'deleted', 'processing'],
            description: 'Filter by status' 
          },
          type: { 
            type: 'string',
            enum: ['video', 'audio', 'image', 'subtitle'],
            description: 'Filter by asset type'
          },
          session_id: { type: 'string', description: 'Filter by session ID' },
          search: { type: 'string', description: 'Full-text search query' },
          sort: { 
            type: 'string', 
            description: 'Sort field and direction (e.g., "created_at:desc")' 
          },
        },
      },
    },
    {
      name: 'streamops_get_asset',
      description: 'Get details for a specific asset',
      inputSchema: {
        type: 'object',
        properties: {
          asset_id: { type: 'string', description: 'Asset ID' },
        },
        required: ['asset_id'],
      },
    },
    {
      name: 'streamops_list_recent_recordings',
      description: 'List recent recordings (convenience method)',
      inputSchema: {
        type: 'object',
        properties: {
          limit: { type: 'number', description: 'Number of recordings to return (default: 50)' },
        },
      },
    },
    {
      name: 'streamops_list_jobs',
      description: 'List jobs with filtering',
      inputSchema: {
        type: 'object',
        properties: {
          state: { 
            type: 'string',
            description: 'Filter by state (comma-separated: running,queued,completed,failed)'
          },
          type: { type: 'string', description: 'Filter by job type' },
          limit: { type: 'number', description: 'Maximum number of jobs to return' },
        },
      },
    },
    {
      name: 'streamops_get_system_summary',
      description: 'Get system status summary',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'streamops_get_drives_status',
      description: 'Get status of all monitored drives',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'streamops_trigger_recording_update',
      description: 'Trigger a manual update of recordings',
      inputSchema: {
        type: 'object',
        properties: {
          drive_path: { type: 'string', description: 'Optional: specific drive path to update' },
        },
      },
    },
    {
      name: 'streamops_get_recent_events',
      description: 'Get recent SSE events (for debugging)',
      inputSchema: {
        type: 'object',
        properties: {
          limit: { type: 'number', description: 'Number of events to retrieve (default: 10)' },
        },
      },
    },
    {
      name: 'streamops_create_job',
      description: 'Create a new processing job for an asset',
      inputSchema: {
        type: 'object',
        properties: {
          asset_id: { type: 'string', description: 'Asset ID to process' },
          job_type: { 
            type: 'string',
            enum: ['remux', 'proxy', 'thumbnail', 'transcode', 'index'],
            description: 'Type of job to create'
          },
          params: { 
            type: 'object', 
            description: 'Job-specific parameters (e.g., container for remux, codec for proxy)',
            properties: {
              container: { type: 'string', description: 'For remux: output container (mov, mp4, mkv)' },
              codec: { type: 'string', description: 'For proxy: codec (dnxhr_lb, prores, h264)' },
              preset: { type: 'string', description: 'For transcode: preset name' },
            }
          }
        },
        required: ['asset_id', 'job_type']
      }
    },
    {
      name: 'streamops_cancel_job',
      description: 'Cancel a running or queued job',
      inputSchema: {
        type: 'object',
        properties: {
          job_id: { type: 'string', description: 'Job ID to cancel' },
        },
        required: ['job_id']
      }
    },
    {
      name: 'streamops_list_rules',
      description: 'List automation rules',
      inputSchema: {
        type: 'object',
        properties: {
          enabled_only: { type: 'boolean', description: 'Only show enabled rules (default: false)' },
        },
      },
    },
    {
      name: 'streamops_toggle_rule',
      description: 'Enable or disable an automation rule',
      inputSchema: {
        type: 'object',
        properties: {
          rule_id: { type: 'string', description: 'Rule ID' },
          enabled: { type: 'boolean', description: 'Enable (true) or disable (false) the rule' },
        },
        required: ['rule_id', 'enabled']
      },
    },
    {
      name: 'streamops_obs_status',
      description: 'Get OBS connection and recording status',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
    {
      name: 'streamops_start_recording',
      description: 'Start OBS recording',
      inputSchema: {
        type: 'object',
        properties: {
          client_name: { type: 'string', description: 'OBS client name (default: "Default OBS")' },
        },
      },
    },
    {
      name: 'streamops_stop_recording',
      description: 'Stop OBS recording',
      inputSchema: {
        type: 'object',
        properties: {
          client_name: { type: 'string', description: 'OBS client name (default: "Default OBS")' },
        },
      },
    },
    {
      name: 'streamops_get_resource_usage',
      description: 'Get current CPU, GPU, memory, and disk usage',
      inputSchema: {
        type: 'object',
        properties: {},
      },
    },
  ],
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'streamops_list_assets': {
        // Map parameters correctly for the API
        const params = {
          page: args.page || 1,
          per_page: args.per_page || 50,
          sort: args.sort || 'created_at:desc',
        };
        
        // Only add optional params if provided
        if (args.status) params.status = args.status;
        if (args.type) params.asset_type = args.type;  // Map 'type' to 'asset_type'
        if (args.session_id) params.session_id = args.session_id;
        if (args.search) params.search = args.search;
        
        const response = await api.get('/assets/', { params }); // Note: trailing slash required
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_get_asset': {
        const response = await api.get(`/assets/${args.asset_id}`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_list_recent_recordings': {
        // Fetch recent recordings from Recording role folders
        // As per user: "recent recordings should only be for all recording role folders"
        const params = {
          per_page: args.limit || 50,
          sort: 'created_at:desc',
          search: 'Recording',  // Search for assets in Recording folders
        };
        
        const response = await api.get('/assets/', { params }); // Note: trailing slash required
        
        // Return the assets directly - they should all be from Recording folders
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify({
                total: response.data.total || response.data.assets?.length || 0,
                assets: response.data.assets || [],
              }, null, 2),
            },
          ],
        };
      }

      case 'streamops_list_jobs': {
        const params = {};
        if (args.state) params.state = args.state;
        if (args.type) params.type = args.type;
        if (args.limit) params.limit = args.limit;
        
        const response = await api.get('/jobs/', { params }); // Note: trailing slash required
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_get_system_summary': {
        const response = await api.get('/system/summary');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_get_drives_status': {
        const response = await api.get('/drives/status');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_trigger_recording_update': {
        // This could trigger a rescan or manual update
        const params = {};
        if (args.drive_path) params.path = args.drive_path;
        
        const response = await api.post('/drives/rescan', params);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_get_recent_events': {
        // For debugging SSE events - this would need an endpoint that stores recent events
        const params = { limit: args.limit || 10 };
        
        try {
          const response = await api.get('/events/recent', { params });
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(response.data, null, 2),
              },
            ],
          };
        } catch (error) {
          // If endpoint doesn't exist, return informative message
          return {
            content: [
              {
                type: 'text',
                text: 'Recent events endpoint not available. SSE events are real-time only.',
              },
            ],
          };
        }
      }

      case 'streamops_create_job': {
        const { asset_id, job_type, params = {} } = args;
        
        // Build job request based on type
        const jobData = {
          asset_id,
          job_type,
          metadata: params
        };
        
        // Map job-specific parameters
        if (job_type === 'remux' && params.container) {
          jobData.metadata.output_format = params.container;
        }
        
        const response = await api.post(`/assets/${asset_id}/jobs`, jobData);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_cancel_job': {
        const response = await api.post(`/jobs/${args.job_id}/cancel`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_list_rules': {
        const params = {};
        if (args.enabled_only) params.enabled = true;
        
        const response = await api.get('/rules/', { params });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_toggle_rule': {
        const { rule_id, enabled } = args;
        const response = await api.patch(`/rules/${rule_id}`, { enabled });
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_obs_status': {
        const response = await api.get('/obs/status');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_start_recording': {
        const client_name = args.client_name || 'Default OBS';
        const response = await api.post(`/obs/clients/${encodeURIComponent(client_name)}/recording/start`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_stop_recording': {
        const client_name = args.client_name || 'Default OBS';
        const response = await api.post(`/obs/clients/${encodeURIComponent(client_name)}/recording/stop`);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      case 'streamops_get_resource_usage': {
        const response = await api.get('/system/stats');
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(response.data, null, 2),
            },
          ],
        };
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: 'text',
          text: formatError(error),
        },
      ],
      isError: true,
    };
  }
});

// Start the server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('StreamOps MCP Server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});