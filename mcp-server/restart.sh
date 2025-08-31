#!/bin/bash

# Restart script for StreamOps MCP Server in Claude Code

echo "Restarting StreamOps MCP server..."

# Kill any existing node processes for the MCP server
pkill -f "node.*streamops/mcp-server/index.js" 2>/dev/null

# Give it a moment to clean up
sleep 1

# Inform user how to add to Claude Code
echo ""
echo "To add this MCP server to Claude Code, run:"
echo ""
echo "claude mcp add streamops 'node /mnt/d/Projects/streamops/mcp-server/index.js'"
echo ""
echo "Or if already added, restart Claude Code to reload the MCP server."
echo ""