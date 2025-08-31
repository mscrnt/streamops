#!/usr/bin/env node

/**
 * Test script for the three operations requested:
 * 1. Get system summary
 * 2. List recent recordings
 * 3. List assets with role=recording filter
 */

import { spawn } from 'child_process';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

let responseCounter = 0;

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
  console.log('=== Testing StreamOps MCP Server - Three Operations ===\n');
  
  // Test 1: Get system summary
  await testOperation('streamops_get_system_summary', {}, 'System Summary');
  
  // Test 2: List recent recordings
  await testOperation('streamops_list_recent_recordings', { limit: 10 }, 'Recent Recordings');
  
  // Test 3: List assets with role filter (simulating role=recording)
  await testOperation('streamops_list_assets', { 
    per_page: 10, 
    sort: 'created_at:desc',
    search: 'Recording'  // This searches for assets in Recording folders
  }, 'Assets with Recording Role');
  
  // Clean up
  mcpServer.kill();
  console.log('\n=== Test Complete ===');
  process.exit(0);
}

async function testOperation(toolName, args, description) {
  console.log(`\n--- ${description} (${toolName}) ---`);
  
  const callToolRequest = {
    jsonrpc: '2.0',
    method: 'tools/call',
    id: ++responseCounter,
    params: {
      name: toolName,
      arguments: args
    }
  };
  
  console.log(`Request: ${JSON.stringify(args)}`);
  mcpServer.stdin.write(JSON.stringify(callToolRequest) + '\n');
  
  // Wait for response
  await new Promise(resolve => {
    mcpServer.stdout.once('data', (data) => {
      try {
        const response = JSON.parse(data.toString());
        if (response.result?.content?.[0]?.text) {
          const result = JSON.parse(response.result.content[0].text);
          
          // Format output based on operation type
          if (toolName === 'streamops_get_system_summary') {
            console.log(`Status: ${result.health?.status || 'unknown'}`);
            console.log(`CPU: ${result.cpu?.percent || 0}%`);
            console.log(`Memory: ${result.memory?.percent || 0}%`);
            console.log(`OBS Connected: ${result.obs?.connected || false}`);
            console.log(`Jobs Running: ${result.jobs?.running || 0}`);
          } else if (toolName === 'streamops_list_recent_recordings') {
            console.log(`Total recordings found: ${result.total || 0}`);
            if (result.assets && result.assets.length > 0) {
              console.log('Latest recordings:');
              result.assets.slice(0, 3).forEach((asset, idx) => {
                console.log(`  ${idx + 1}. ${asset.filename} (${asset.metadata?.duration || 0}s)`);
              });
            }
          } else if (toolName === 'streamops_list_assets') {
            console.log(`Total assets found: ${result.total || 0}`);
            if (result.assets && result.assets.length > 0) {
              console.log('Latest assets from Recording folders:');
              result.assets.slice(0, 3).forEach((asset, idx) => {
                console.log(`  ${idx + 1}. ${asset.filename} (${asset.metadata?.duration || 0}s)`);
              });
            }
          }
        } else if (response.result?.isError) {
          console.log('❌ Error:', response.result.content[0].text);
        }
      } catch (e) {
        console.error('❌ Failed to parse response:', e.message);
        console.log('Raw response:', data.toString());
      }
      resolve();
    });
  });
}

// Run tests after a short delay to ensure server is ready
setTimeout(runTests, 500);

// Handle errors
mcpServer.on('error', (err) => {
  console.error('Failed to start MCP server:', err);
  process.exit(1);
});