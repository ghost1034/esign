import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  timeout: 60000,
  use: { baseURL: 'http://127.0.0.1:3101', browserName: 'chromium', screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: 'npx next dev --port 3101 --hostname 127.0.0.1', url: 'http://127.0.0.1:3101', reuseExistingServer: false, timeout: 120000,
    env: { NEXT_DIST_DIR: '.next-test', NEXT_PUBLIC_APP_ENV: 'local', NEXT_PUBLIC_LOCAL_AUTH_BYPASS: 'true' } },
})
