const { test, expect } = require('@playwright/test');

test.describe('Rules Page Complete Workflow', () => {
  test('should create a rule from preset with all settings', async ({ page }) => {
    // Navigate to Rules page
    await page.goto('http://localhost:7767/app/rules');
    
    // Wait for page to load
    await page.waitForSelector('h1:has-text("Automation Rules")');
    
    // Click "Use Preset" button
    await page.click('button:has-text("Use Preset")');
    
    // Wait for presets to appear
    await page.waitForSelector('.grid');
    
    // Select the "Generate Thumbnails" preset
    const presetCard = page.locator('text=Generate Thumbnails & Previews').first();
    await presetCard.click();
    
    // Wait for the rule composer to open
    await page.waitForSelector('h3:has-text("Create Rule from Preset")');
    
    // Verify preset data is loaded
    const ruleNameInput = page.locator('input[placeholder="Enter rule name"]');
    await expect(ruleNameInput).toHaveValue('Generate Thumbnails');
    
    // Check that conditions are pre-populated
    const conditionFields = page.locator('text=File Extension');
    await expect(conditionFields).toBeVisible();
    
    // Check that actions are pre-populated  
    const actionSection = page.locator('text=Generate Thumbnails');
    await expect(actionSection).toBeVisible();
    
    // Test guardrails section
    await page.click('text=Guardrails');
    
    // Enable "Pause while recording" checkbox
    const pauseCheckbox = page.locator('text=Pause while recording').locator('..').locator('input[type="checkbox"]');
    await pauseCheckbox.check();
    
    // Verify quiet period field appears
    const quietPeriodInput = page.locator('input[type="number"][min="0"][max="3600"]');
    await expect(quietPeriodInput).toBeVisible();
    await expect(quietPeriodInput).toHaveValue('45');
    
    // Change quiet period to 60 seconds
    await quietPeriodInput.fill('60');
    
    // Test dropdown functionality - change a condition operator
    const operatorDropdown = page.locator('button').filter({ hasText: 'in' }).first();
    await operatorDropdown.click();
    
    // Select "equals" from dropdown
    await page.click('text=equals');
    
    // Add a new action - test Move action with role-based target
    await page.click('button:has-text("Add Action")');
    
    // Select "Move File" from action type dropdown
    const actionDropdown = page.locator('button').filter({ hasText: 'Select action...' }).first();
    await actionDropdown.click();
    await page.click('text=Move File');
    
    // Wait for target folder dropdown to load drive roles
    await page.waitForTimeout(500); // Give time for API call
    
    // Check if target dropdown shows role-based paths
    const targetDropdown = page.locator('button').filter({ hasText: 'Select target...' }).first();
    await targetDropdown.click();
    
    // Verify role-based paths are available
    const editingOption = page.locator('text=/mnt/drive_e/Editing');
    await expect(editingOption).toBeVisible();
    
    // Select the editing path
    await editingOption.click();
    
    // Save the rule
    await page.click('button:has-text("Save Rule")');
    
    // Wait for success message or rule to appear in list
    await page.waitForSelector('text=Rule created successfully', { timeout: 10000 });
    
    // Verify rule appears in the list
    await page.waitForSelector('table');
    const ruleRow = page.locator('tr').filter({ hasText: 'Generate Thumbnails' });
    await expect(ruleRow).toBeVisible();
    
    // Verify rule is active
    const activeStatus = ruleRow.locator('text=Active');
    await expect(activeStatus).toBeVisible();
    
    // Test toggle functionality
    const pauseButton = ruleRow.locator('button').filter({ has: page.locator('svg') }).first();
    await pauseButton.click();
    
    // Wait for status to update
    await page.waitForSelector('text=Paused');
    
    // Verify rule shows as paused
    const pausedStatus = ruleRow.locator('text=Paused');
    await expect(pausedStatus).toBeVisible();
  });
  
  test('should create custom rule without preset', async ({ page }) => {
    // Navigate to Rules page
    await page.goto('http://localhost:7767/app/rules');
    
    // Click "Create Custom Rule"
    await page.click('button:has-text("Create Custom Rule")');
    
    // Wait for composer
    await page.waitForSelector('h3:has-text("Create Custom Rule")');
    
    // Enter rule name
    const nameInput = page.locator('input[placeholder="Enter rule name"]');
    await nameInput.fill('Archive Old Recordings');
    
    // Add a condition
    await page.click('button:has-text("Add Condition")');
    
    // Select field
    const fieldDropdown = page.locator('button').filter({ hasText: 'Select field...' }).first();
    await fieldDropdown.click();
    await page.click('text=Age (days)');
    
    // Select operator
    const operatorDropdown = page.locator('button').filter({ hasText: 'Select operator...' }).first();
    await operatorDropdown.click();
    await page.click('text=Greater Than');
    
    // Enter value
    const valueInput = page.locator('input[placeholder="Value"]').first();
    await valueInput.fill('30');
    
    // Add an action
    await page.click('button:has-text("Add Action")');
    
    // Select action type
    const actionDropdown = page.locator('button').filter({ hasText: 'Select action...' }).first();
    await actionDropdown.click();
    await page.click('text=Move File');
    
    // Select target from roles
    const targetDropdown = page.locator('button').filter({ hasText: 'Select target...' }).first();
    await targetDropdown.click();
    
    // Select archive path
    const archiveOption = page.locator('text=/mnt/drive_d/Archive').first();
    if (await archiveOption.isVisible()) {
      await archiveOption.click();
    } else {
      // If no archive role, select any available path
      await page.keyboard.press('Escape');
      const targetInput = page.locator('input[placeholder="Target folder"]').first();
      await targetInput.fill('/mnt/drive_d/Archive');
    }
    
    // Enable guardrails
    await page.click('text=Guardrails');
    await page.locator('text=Pause while recording').locator('..').locator('input[type="checkbox"]').check();
    
    // Verify quiet period appears and set to 30
    const quietPeriod = page.locator('input[type="number"][min="0"][max="3600"]');
    await expect(quietPeriod).toBeVisible();
    await quietPeriod.fill('30');
    
    // Save the rule
    await page.click('button:has-text("Save Rule")');
    
    // Verify success
    await page.waitForSelector('text=Rule created successfully', { timeout: 10000 });
  });
});