import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:3100', browserName: 'chromium', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: 'npm run dev:frontend -- --hostname 127.0.0.1', url: 'http://127.0.0.1:3100', reuseExistingServer: !process.env.CI, timeout: 120000,
    env: { NEXT_PUBLIC_APP_ENV: 'local', NEXT_PUBLIC_LOCAL_AUTH_BYPASS: 'true' } },
})
