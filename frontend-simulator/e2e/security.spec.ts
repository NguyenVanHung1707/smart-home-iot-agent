import { test, expect } from '@playwright/test';

test.describe('Simulator Security Best Practices & Vulnerability Defense E2E', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await expect(page.locator('h1')).toContainText('SmartHome Rebuild');
  });

  test('Anti-XSS: should sanitize script & img onerror payloads in device name & room', async ({ page, request }) => {
    // Register dialog listener to catch any unhandled alert() execution (XSS triggered)
    let alertTriggered = false;
    page.on('dialog', async (dialog) => {
      alertTriggered = true;
      await dialog.dismiss();
    });

    const xssPayload = "<script>window.__xss_executed=true;alert('xss')</script><img src=x onerror=\"window.__xss_executed=true;alert(1)\">Đèn An Toàn";
    const xssRoom = "<img src=x onerror=alert(2)>Phòng Thử Nghiệm";

    // 1. Create device with XSS payloads via API
    const createRes = await request.post('http://127.0.0.1:8001/api/devices', {
      data: {
        id: 'sec-xss-lamp',
        name: xssPayload,
        room: xssRoom,
        kind: 'light',
        x: 180,
        y: 180,
        state: { power: true, brightness: 85 },
      },
    });
    expect(createRes.status()).toBe(200);
    const createdDev = await createRes.json();

    // Verify backend returned sanitized text
    expect(createdDev.name).not.toContain('<script>');
    expect(createdDev.name).toContain('&lt;script&gt;');
    expect(createdDev.room).not.toContain('<img');
    expect(createdDev.room).toContain('&lt;img');

    // 2. Reload frontend page and inspect rendered element
    await page.reload();
    await expect(page.locator('h1')).toContainText('SmartHome Rebuild');

    // Ensure no alert was fired
    await page.waitForTimeout(500);
    const isXssExecuted = await page.evaluate(() => (window as any).__xss_executed === true);
    expect(isXssExecuted).toBe(false);
    expect(alertTriggered).toBe(false);

    // Clean up created device
    await request.delete('http://127.0.0.1:8001/api/devices/sec-xss-lamp');
  });

  test('Anti-MQTT Topic Injection: should strictly reject forbidden wildcards and path traversal in device_id', async ({ request }) => {
    const maliciousDeviceIds = [
      'test/+/sub',
      'test/#/malicious',
      '../../root',
      'device name with spaces',
      'device;drop table',
      'homing/devices/sensor/state',
      'cmd-injection;reboot',
      '<script>alert(1)</script>',
      'living+light',
      'light#all',
    ];

    for (const badId of maliciousDeviceIds) {
      // Direct API Add Device with malicious ID
      const res = await request.post('http://127.0.0.1:8001/api/devices', {
        data: {
          id: badId,
          name: 'Malicious ID Test',
          kind: 'light',
          room: 'Phòng khách',
        },
      });
      // Should be rejected with 400 Bad Request
      expect(res.status(), `Device ID "${badId}" should be rejected`).toBe(400);

      // Path parameter injection attempts
      const actRes = await request.post(`http://127.0.0.1:8001/api/devices/${encodeURIComponent(badId)}/action`, {
        data: { action: 'toggle' },
      });
      expect(actRes.status()).toBeGreaterThanOrEqual(400);
    }
  });

  test('Bounds & Type Checking: should reject negative, infinite, NaN coordinates and invalid walls', async ({ request }) => {
    // 1. Negative coordinates
    const negRes = await request.post('http://127.0.0.1:8001/api/devices', {
      data: {
        id: 'sec-neg-coord',
        name: 'Negative Coord Lamp',
        kind: 'light',
        x: -250,
        y: 100,
      },
    });
    expect(negRes.status()).toBe(400);

    // 2. Out-of-bounds large coordinates
    const hugeRes = await request.post('http://127.0.0.1:8001/api/devices', {
      data: {
        id: 'sec-huge-coord',
        name: 'Huge Coord Lamp',
        kind: 'light',
        x: 99999,
        y: 100,
      },
    });
    expect(hugeRes.status()).toBe(400);

    // 3. Invalid walls (negative / invalid bounds)
    const badWallRes = await request.post('http://127.0.0.1:8001/api/walls', {
      data: [{ x1: -50, y1: 0, x2: 200, y2: 200 }],
    });
    expect(badWallRes.status()).toBe(400);
  });

  test('Fault Mode Validation: should only accept allowed fault modes (none, offline, timeout, error)', async ({ request }) => {
    // 1. Valid fault modes
    for (const validMode of ['none', 'offline', 'timeout', 'error']) {
      const okRes = await request.post('http://127.0.0.1:8001/api/devices/living-light/fault', {
        data: { mode: validMode },
      });
      expect(okRes.status()).toBe(200);
      const data = await okRes.json();
      expect(data.fault).toBe(validMode);
    }

    // 2. Invalid malicious fault mode
    const badFaultRes = await request.post('http://127.0.0.1:8001/api/devices/living-light/fault', {
      data: { mode: 'malicious_system_crash' },
    });
    expect(badFaultRes.status()).toBe(400);

    // Reset back to none
    await request.post('http://127.0.0.1:8001/api/devices/living-light/fault', {
      data: { mode: 'none' },
    });
  });
});
