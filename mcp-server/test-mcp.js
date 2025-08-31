#!/usr/bin/env node

/**
 * Test script for StreamOps MCP Server
 * Tests the MCP server can communicate with the API properly
 */

import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

// Start the MCP server
const mcpServer = spawn('node', [join(__dirname, 'index.js')], {
  stdio: ['pipe', 'pipe', 'pipe'],
  env: { ...process.env, STREAMOPS_API_URL: 'http://localhost:7767/api' }
});

// Handle server output
mcpServer.stderr.on('data', (data) => {
  console.log('Server started:', data.toString().trim());
});

// Send test requests
async function runTests() {
  console.log('Running MCP server tests...\n');
  
  // Test 1: List tools request
  const listToolsRequest = {
    jsonrpc: '2.0',
    method: 'tools/list',
    id: 1
  };
  
  console.log('Sending list tools request...');
  mcpServer.stdin.write(JSON.stringify(listToolsRequest) + '\n');
  
  // Wait for response
  await new Promise(resolve => {
    mcpServer.stdout.once('data', (data) => {
      try {
        const response = JSON.parse(data.toString());
        console.log('Tools available:', response.result.tools.length);
        response.result.tools.forEach(tool => {
          console.log(`  - ${tool.name}: ${tool.description}`);
        });
      } catch (e) {
        console.error('Failed to parse response:', e.message);
      }
      resolve();
    });
  });
  
  // Test 2: Call a tool (get system summary)
  const callToolRequest = {
    jsonrpc: '2.0',
    method: 'tools/call',
    id: 2,
    params: {
      name: 'streamops_get_system_summary',
      arguments: {}
    }
  };
  
  console.log('\nCalling streamops_get_system_summary...');
  mcpServer.stdin.write(JSON.stringify(callToolRequest) + '\n');
  
  // Wait for response
  await new Promise(resolve => {
    mcpServer.stdout.once('data', (data) => {
      try {
        const response = JSON.parse(data.toString());
        if (response.result?.content?.[0]?.text) {
          const summary = JSON.parse(response.result.content[0].text);
          console.log('System Summary:', JSON.stringify(summary, null, 2));
        } else if (response.result?.isError) {
          console.log('Error:', response.result.content[0].text);
        }
      } catch (e) {
        console.error('Failed to parse response:', e.message);
      }
      resolve();
    });
  });
  
  // Clean up
  mcpServer.kill();
  process.exit(0);
}

// Run tests after a short delay to ensure server is ready
setTimeout(runTests, 500);

// Handle errors
mcpServer.on('error', (err) => {
  console.error('Failed to start MCP server:', err);
  process.exit(1);
});