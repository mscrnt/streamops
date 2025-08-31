import { test, expect } from '@playwright/test';

test.describe('StreamOps Dashboard', () => {
  test('should load dashboard without errors', async ({ page }) => {
    // Listen for console errors
    const errors = [];
    page.on('console', msg => {
      if (msg.type() === 'error') {
        errors.push(msg.text());
      }
    });

    // Listen for page errors
    page.on('pageerror', error => {
      errors.push(error.message);
    });

    // Navigate to dashboard
    await page.goto('/');
    
    // Wait for the page to load
    await page.waitForLoadState('networkidle');
    
    // Check that the dashboard loaded
    await expect(page.locator('h1, h2').first()).toBeVisible({ timeout: 5000 });
    
    // Check for console errors
    console.log('Console errors found:', errors);
    expect(errors).toHaveLength(0);
  });

  test('should check API endpoints', async ({ page, request }) => {
    // Test the assets endpoint
    const assetsResponse = await request.get('/api/assets?sort=created_at:desc&page=1&per_page=50');
    console.log('Assets endpoint status:', assetsResponse.status());
    
    if (assetsResponse.status() !== 200) {
      const body = await assetsResponse.text();
      console.log('Assets endpoint error response:', body);
    }
    
    expect(assetsResponse.status()).toBe(200);
    
    // Test the assets endpoint with source=recording
    const recordingsResponse = await request.get('/api/assets?source=recording&sort_by=created_at&sort_order=desc&per_page=50');
    console.log('Recordings endpoint status:', recordingsResponse.status());
    
    if (recordingsResponse.status() !== 200) {
      const body = await recordingsResponse.text();
      console.log('Recordings endpoint error response:', body);
    }
    
    expect(recordingsResponse.status()).toBe(200);
    
    // Test system summary endpoint
    const systemResponse = await request.get('/api/system/summary');
    expect(systemResponse.status()).toBe(200);
    
    // Test drives status endpoint
    const drivesResponse = await request.get('/api/drives/status');
    expect(drivesResponse.status()).toBe(200);
  });

  test('should check recent recordings panel', async ({ page }) => {
    await page.goto('/');
    
    // Wait for recent recordings panel to load
    const recordingsPanel = page.locator('text="Recent Recordings"').first();
    await expect(recordingsPanel).toBeVisible({ timeout: 10000 });
    
    // Check if "No recent recordings" message is shown or if recordings are listed
    const noRecordingsMsg = page.locator('text="No recent recordings from watched folders"');
    const recordingsList = page.locator('[data-testid="recording-item"]');
    
    // Either we should have no recordings message or actual recordings
    const hasNoRecordingsMsg = await noRecordingsMsg.isVisible().catch(() => false);
    const hasRecordings = await recordingsList.first().isVisible().catch(() => false);
    
    console.log('Has "no recordings" message:', hasNoRecordingsMsg);
    console.log('Has recordings:', hasRecordings);
    
    // At least one should be true
    expect(hasNoRecordingsMsg || hasRecordings).toBeTruthy();
  });

  test('should check EventSource connection', async ({ page }) => {
    await page.goto('/');
    
    // Evaluate EventSource connection in the browser
    const eventSourceStatus = await page.evaluate(() => {
      return new Promise((resolve) => {
        const eventSource = new EventSource('/api/events/stream');
        let connected = false;
        
        eventSource.onopen = () => {
          connected = true;
          eventSource.close();
          resolve({ connected: true, error: null });
        };
        
        eventSource.onerror = (error) => {
          eventSource.close();
          resolve({ connected: false, error: error.message || 'Connection failed' });
        };
        
        // Timeout after 5 seconds
        setTimeout(() => {
          eventSource.close();
          resolve({ connected, error: connected ? null : 'Timeout' });
        }, 5000);
      });
    });
    
    console.log('EventSource connection status:', eventSourceStatus);
    expect(eventSourceStatus.connected).toBeTruthy();
  });

  test('should navigate to Assets page', async ({ page }) => {
    await page.goto('/');
    
    // Click on Assets in the navigation
    await page.click('text=Assets');
    
    // Wait for navigation
    await page.waitForURL('**/assets');
    
    // Check for error messages
    const errorMsg = page.locator('text="Server error"');
    const hasError = await errorMsg.isVisible().catch(() => false);
    
    if (hasError) {
      console.log('Assets page has server error');
      
      // Check network requests for more details
      const response = await page.waitForResponse(
        response => response.url().includes('/api/assets') && response.status() === 500,
        { timeout: 5000 }
      ).catch(() => null);
      
      if (response) {
        const body = await response.text();
        console.log('500 error response body:', body);
      }
    }
    
    expect(hasError).toBeFalsy();
  });
});