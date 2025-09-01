#!/usr/bin/env node

/**
 * Test script for enhanced StreamOps MCP Server
 * Tests the new tools added to the MCP server
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

// Keep track of request ID
let requestId = 1;

// Helper to send request and wait for response
async function sendRequest(method, params = {}) {
  const request = {
    jsonrpc: '2.0',
    method,
    params,
    id: requestId++
  };
  
  console.log(`\n→ Sending: ${method}`);
  mcpServer.stdin.write(JSON.stringify(request) + '\n');
  
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => {
      reject(new Error('Request timeout'));
    }, 5000);
    
    mcpServer.stdout.once('data', (data) => {
      clearTimeout(timeout);
      try {
        const response = JSON.parse(data.toString());
        resolve(response);
      } catch (e) {
        reject(e);
      }
    });
  });
}

// Run tests
async function runTests() {
  console.log('🧪 Testing Enhanced StreamOps MCP Server\n');
  console.log('=' .repeat(50));
  
  try {
    // Wait for server to start
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // Test 1: List tools to verify new ones are added
    console.log('\n📋 Test 1: List all available tools');
    const toolsResponse = await sendRequest('tools/list');
    const tools = toolsResponse.result.tools;
    console.log(`✓ Found ${tools.length} tools`);
    
    // Check for new tools
    const newTools = [
      'streamops_create_job',
      'streamops_cancel_job',
      'streamops_list_rules',
      'streamops_toggle_rule',
      'streamops_obs_status',
      'streamops_start_recording',
      'streamops_stop_recording',
      'streamops_get_resource_usage'
    ];
    
    const foundTools = tools.map(t => t.name);
    newTools.forEach(toolName => {
      if (foundTools.includes(toolName)) {
        console.log(`  ✓ ${toolName} found`);
      } else {
        console.log(`  ✗ ${toolName} NOT FOUND`);
      }
    });
    
    // Test 2: Get OBS status
    console.log('\n🎥 Test 2: Get OBS Status');
    const obsResponse = await sendRequest('tools/call', {
      name: 'streamops_obs_status',
      arguments: {}
    });
    const obsData = JSON.parse(obsResponse.result.content[0].text);
    console.log(`✓ OBS connections: ${obsData.connected} connected, ${obsData.disconnected} disconnected`);
    console.log(`  Recording: ${obsData.recording > 0 ? 'Yes' : 'No'}`);
    
    // Test 3: Get resource usage
    console.log('\n💻 Test 3: Get Resource Usage');
    const resourceResponse = await sendRequest('tools/call', {
      name: 'streamops_get_resource_usage',
      arguments: {}
    });
    const resourceData = JSON.parse(resourceResponse.result.content[0].text);
    console.log(`✓ CPU: ${resourceData.cpu?.percent || 0}%`);
    console.log(`  Memory: ${resourceData.memory?.percent || 0}%`);
    console.log(`  GPU: ${resourceData.gpu?.utilization || 0}%`);
    
    // Test 4: List rules
    console.log('\n📜 Test 4: List Rules');
    const rulesResponse = await sendRequest('tools/call', {
      name: 'streamops_list_rules',
      arguments: { enabled_only: false }
    });
    const rulesData = JSON.parse(rulesResponse.result.content[0].text);
    const ruleCount = Array.isArray(rulesData) ? rulesData.length : (rulesData.rules?.length || 0);
    console.log(`✓ Found ${ruleCount} rules`);
    
    // Test 5: List recent jobs
    console.log('\n⚙️ Test 5: List Recent Jobs');
    const jobsResponse = await sendRequest('tools/call', {
      name: 'streamops_list_jobs',
      arguments: { limit: 5 }
    });
    const jobsData = JSON.parse(jobsResponse.result.content[0].text);
    const jobCount = Array.isArray(jobsData) ? jobsData.length : (jobsData.jobs?.length || 0);
    console.log(`✓ Found ${jobCount} recent jobs`);
    
    console.log('\n' + '=' .repeat(50));
    console.log('✅ All tests completed successfully!\n');
    
  } catch (error) {
    console.error('\n❌ Test failed:', error.message);
    if (error.stack) {
      console.error(error.stack);
    }
  } finally {
    // Clean up
    mcpServer.kill();
    process.exit(0);
  }
}

// Handle server errors
mcpServer.stderr.on('data', (data) => {
  const msg = data.toString().trim();
  if (msg) {
    console.error('Server error:', msg);
  }
});

// Start tests
runTests();