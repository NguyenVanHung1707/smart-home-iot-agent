import { test, expect } from '@playwright/test';

test.describe('Terra Smart Desktop E2E Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to Simulator Web App
    await page.goto('/');
    // Wait for the app header to be visible
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('h1')).toContainText('SmartHome Rebuild');
  });

  test('should display full Desktop UI components: TopAppBar, NavigationDrawer, 2D Canvas, Device Library, MQTT Console', async ({ page }) => {
    // 1. TopAppBar verification
    await expect(page.getByRole('button', { name: /Mặt bằng 2D/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Không gian 3D/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Discovery Scan/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Reset Demo/i })).toBeVisible();

    // 2. Navigation Drawer (Rooms & Devices Explorer)
    await expect(page.getByText('Khu Vực & Phòng Ở')).toBeVisible();
    await expect(page.getByRole('button', { name: /Toàn Bộ Ngôi Nhà/i })).toBeVisible();
    await expect(page.getByText(/Thiết bị \(\d+\)/)).toBeVisible();

    // 3. 2D Canvas Editor Toolbar & Canvas
    await expect(page.getByRole('button', { name: /Chọn/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Vẽ tường/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /Xoá tường/i })).toBeVisible();
    const canvas = page.locator('main canvas');
    await expect(canvas).toBeVisible();

    // 4. Right Sidebar: Device Library
    await expect(page.getByRole('heading', { name: 'Thư viện Thiết bị' })).toBeVisible();
    await expect(page.getByPlaceholder('Tìm theo tên hoặc phòng...')).toBeVisible();
    await expect(page.getByRole('button', { name: /Thêm Mới/i })).toBeVisible();

    // 5. Bottom Panel: Open and verify MQTT Console Sandbox
    await page.getByRole('button', { name: /MQTT Console/i }).first().click();
    await expect(page.getByText('MQTT Sandbox Console')).toBeVisible();
    await expect(page.getByRole('button', { name: /Quét Thiết Bị \(Scan\)/i })).toBeVisible();
  });

  test('should switch smoothly between 2D Plan and 3D View with Three.js rendering', async ({ page }) => {
    // Switch to 3D View
    const btn3D = page.getByRole('button', { name: /Không gian 3D/i });
    await btn3D.click();

    // Check 3D container & Three.js canvas
    await expect(page.getByText('Không gian 3D tương tác')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Isometric' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Top-Down' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Chính diện' })).toBeVisible();
    await expect(page.getByRole('button', { name: /Reset Camera/i })).toBeVisible();

    // Verify WebGL Canvas is present
    const webglCanvas = page.locator('main canvas');
    await expect(webglCanvas).toBeVisible();

    // Test Camera preset switches
    await page.getByRole('button', { name: 'Top-Down' }).click();
    await page.waitForTimeout(300);
    await page.getByRole('button', { name: 'Isometric' }).click();
    await page.waitForTimeout(300);

    // Switch back to 2D Plan
    const btn2D = page.getByRole('button', { name: /Mặt bằng 2D/i });
    await btn2D.click();
    await expect(page.getByRole('button', { name: /Chọn \/ Di chuyển/i })).toBeVisible();
  });

  test('should select a device, control power & brightness, and verify MQTT log updates', async ({ page }) => {
    // Select "Đèn phòng khách" from device navigation
    const deviceItem = page.getByRole('button', { name: /Đèn phòng khách/i }).first();
    await expect(deviceItem).toBeVisible();
    await deviceItem.click();

    // Device Inspector should now be visible
    await expect(page.getByRole('heading', { name: 'Đèn phòng khách' })).toBeVisible();
    await expect(page.getByText('Nguồn điện thiết bị')).toBeVisible();

    // Toggle power
    const powerBtn = page.getByRole('button', { name: /Tắt Thiết Bị|Bật Thiết Bị/i });
    await expect(powerBtn).toBeVisible();
    const initialText = await powerBtn.textContent();
    await powerBtn.click();

    // Verify power button state toggles
    await expect(powerBtn).not.toHaveText(initialText || '');

    // Adjust brightness slider if present
    const slider = page.locator('input[type="range"]').first();
    if (await slider.isVisible()) {
      await slider.fill('65');
      await slider.dispatchEvent('change');
    }

    // Open MQTT console if not already open
    if (!(await page.locator('footer').isVisible())) {
      await page.getByRole('button', { name: /MQTT Console/i }).first().click();
    }

    // Verify MQTT Console captures command and ack
    const consoleLogs = page.locator('footer');
    await expect(consoleLogs).toContainText(/homing\/devices\/living-light/);
  });

  test('should expand 2D canvas to full height without blank gaps when hiding MQTT console', async ({ page }) => {
    const canvas = page.locator('main canvas');
    await expect(canvas).toBeVisible();

    // Ensure MQTT Console is open at bottom
    if (!(await page.locator('footer').isVisible())) {
      await page.getByRole('button', { name: /MQTT Console/i }).first().click();
    }

    // 1. Initial dimensions with MQTT Console open at bottom
    await expect(page.locator('footer')).toBeVisible();
    const initialCanvasHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.clientHeight);
    const initialWrapperHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.parentElement?.clientHeight ?? 0);

    expect(initialCanvasHeight).toBeGreaterThan(200);
    expect(Math.abs(initialCanvasHeight - initialWrapperHeight)).toBeLessThanOrEqual(2);

    // 2. Hide MQTT Console
    const hideConsoleBtn = page.getByTitle('Ẩn MQTT Console', { exact: true });
    if (await hideConsoleBtn.isVisible()) {
      await hideConsoleBtn.click();
    } else {
      await page.getByRole('button', { name: /MQTT Console/i }).first().click();
    }

    // Wait for console to close and ResizeObserver to update canvas
    await expect(page.locator('footer')).not.toBeVisible();
    await page.waitForTimeout(300);

    // 3. Verify Canvas & Wrapper expanded to fill the entire vertical space
    const expandedCanvasHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.clientHeight);
    const expandedWrapperHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.parentElement?.clientHeight ?? 0);
    const inlineStyleHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.style.height);

    // Canvas must expand by at least ~150px (the bottom console height)
    expect(expandedCanvasHeight).toBeGreaterThan(initialCanvasHeight + 100);
    // Canvas must fill 100% of wrapper without clipping or blank gap
    expect(Math.abs(expandedCanvasHeight - expandedWrapperHeight)).toBeLessThanOrEqual(2);
    // Canvas inline style.height must NOT be hardcoded in px
    expect(inlineStyleHeight).not.toContain('px');

    // 4. Reopen MQTT Console and verify it resizes back smoothly
    const reopenBtn = page.getByRole('button', { name: /Mở lại MQTT Console|MQTT Console/i }).first();
    await reopenBtn.click();
    await expect(page.locator('footer')).toBeVisible();
    await page.waitForTimeout(300);

    const restoredCanvasHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.clientHeight);
    const restoredWrapperHeight = await canvas.evaluate((el: HTMLCanvasElement) => el.parentElement?.clientHeight ?? 0);
    expect(Math.abs(restoredCanvasHeight - restoredWrapperHeight)).toBeLessThanOrEqual(2);
    expect(restoredCanvasHeight).toBeLessThan(expandedCanvasHeight - 100);
  });
});
