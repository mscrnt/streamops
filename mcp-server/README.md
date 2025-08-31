# StreamOps MCP Server

MCP (Model Context Protocol) server for StreamOps API integration with Claude Code.

## Setup

1. Install dependencies (already done):
```bash
npm install
```

2. Add to Claude Code:
```bash
claude mcp add streamops 'node /mnt/d/Projects/streamops/mcp-server/index.js'
```

3. Restart Claude Code to load the MCP server

## Available Tools

The MCP server provides these tools to Claude:

- `streamops_list_assets` - List assets with filtering and pagination
- `streamops_get_asset` - Get details for a specific asset
- `streamops_list_recent_recordings` - List recent recordings from Recording folders
- `streamops_list_jobs` - List jobs with filtering
- `streamops_get_system_summary` - Get system status summary
- `streamops_get_drives_status` - Get status of all monitored drives
- `streamops_trigger_recording_update` - Trigger a manual update of recordings
- `streamops_get_recent_events` - Get recent SSE events (for debugging)

## Testing

Run the test script to verify the MCP server is working:
```bash
node test-mcp.js
```

## Troubleshooting

If the MCP server isn't working:

1. Check the StreamOps API is running:
```bash
curl http://localhost:7767/api/health
```

2. Test the MCP server directly:
```bash
node test-mcp.js
```

3. Restart Claude Code after adding/updating the MCP server

## Configuration

The server uses environment variable `STREAMOPS_API_URL` (default: `http://localhost:7767/api`).

## Recent Fixes

- Fixed API endpoints to include required trailing slashes (`/assets/`, `/jobs/`)
- Updated recent recordings to filter by Recording role folders (not asset type)
- Properly maps response structure (`response.data.assets` not `response.data.items`)