import { defineConfig } from '@playwright/test';

const port = 8765;
const baseURL = `http://127.0.0.1:${port}`;
const python = process.env.PYTHON || 'python';
const pythonCommand = python.includes(' ') ? `"${python}"` : python;
const slowMo = Number(process.env.PLAYWRIGHT_SLOW_MO || 0);

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.e2e.spec.ts',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL,
    launchOptions: { slowMo },
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { browserName: 'chromium' },
    },
  ],
  globalSetup: './tests/global-setup.ts',
  webServer: {
    command: `${pythonCommand} manage.py runserver 127.0.0.1:${port} --noreload --settings=config.e2e_settings`,
    url: `${baseURL}/healthz/`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
