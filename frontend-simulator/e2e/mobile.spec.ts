import { test, expect } from '@playwright/test';

test.describe('Terra Smart Mobile Responsiveness & Touch UX Tests', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('h1')).toContainText('SmartHome Rebuild');
  });

  test('should render responsive mobile layout with bottom navigation bar without layout overflow', async ({ page }) => {
    // Check TopAppBar is visible and styled properly
    const header = page.locator('header');
    await expect(header).toBeVisible();

    // Check Bottom Navigation Bar on Mobile
    const bottomNav = page.locator('nav');
    await expect(bottomNav).toBeVisible();
    await expect(bottomNav.getByRole('button', { name: /Mặt Bằng/i })).toBeVisible();
    await expect(bottomNav.getByRole('button', { name: /Phòng Ở/i })).toBeVisible();
    await expect(bottomNav.getByRole('button', { name: /Thư Viện|Chi Tiết/i })).toBeVisible();
    await expect(bottomNav.getByRole('button', { name: /MQTT Log/i })).toBeVisible();

    // Verify Main 2D Canvas is visible
    const canvas = page.locator('main canvas');
    await expect(canvas).toBeVisible();

    // Verify viewport bounds: page does not have horizontal scrollbar
    const scrollWidth = await page.evaluate(() => document.documentElement.scrollWidth);
    const clientWidth = await page.evaluate(() => document.documentElement.clientWidth);
    expect(scrollWidth).toBeLessThanOrEqual(clientWidth + 2);
  });

  test('should navigate rooms, select device, and control operations on mobile', async ({ page }) => {
    const bottomNav = page.locator('nav');

    // Tap "Phòng Ở" tab to view rooms & device explorer
    await bottomNav.getByRole('button', { name: /Phòng Ở/i }).click();
    await expect(page.getByText('Khu Vực & Phòng Ở')).toBeVisible();

    // Tap on a device item (e.g. "Đèn phòng khách")
    const deviceItem = page.getByRole('button', { name: /Đèn phòng khách/i }).first();
    await expect(deviceItem).toBeVisible();
    await deviceItem.click();

    // Check that Device Inspector is opened in mobile view
    await expect(page.getByRole('heading', { name: 'Đèn phòng khách' })).toBeVisible();
    await expect(page.getByText('Nguồn điện thiết bị')).toBeVisible();

    // Toggle power button on mobile
    const powerBtn = page.getByRole('button', { name: /Tắt Thiết Bị|Bật Thiết Bị/i });
    await expect(powerBtn).toBeVisible();
    const prevText = await powerBtn.textContent();
    await powerBtn.click();
    await expect(powerBtn).not.toHaveText(prevText || '');

    // Close Inspector to return to canvas
    const closeBtn = page.getByTitle('Đóng bảng điều khiển');
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
    }
  });

  test('should switch between 2D and 3D on mobile and view MQTT Console logs', async ({ page }) => {
    const bottomNav = page.locator('nav');

    // Go to Map tab
    await bottomNav.getByRole('button', { name: /Mặt Bằng/i }).click();

    // Switch to 3D View on mobile
    const btn3D = page.getByRole('button', { name: /Không gian 3D/i });
    await btn3D.click();

    // Verify Three.js Canvas renders on mobile
    const webglCanvas = page.locator('main canvas');
    await expect(webglCanvas).toBeVisible();

    // Switch back to 2D
    const btn2D = page.getByRole('button', { name: /Mặt bằng 2D/i });
    await btn2D.click();
    await expect(page.locator('main canvas')).toBeVisible();

    // Open MQTT Log tab
    await bottomNav.getByRole('button', { name: /MQTT Log/i }).click();
    await expect(page.getByText('MQTT Sandbox Console').first()).toBeVisible();
  });
});
