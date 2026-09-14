import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  workers: 1,
  timeout: 120000,
  expect: { timeout: 15000 },
  use: {
    baseURL: 'http://127.0.0.1:3102',
    browserName: 'chromium',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'node scripts/sync-pdf-worker.mjs && npx next dev --hostname 127.0.0.1 --port 3102',
    url: 'http://127.0.0.1:3102',
    reuseExistingServer: false,
    timeout: 120000,
    env: {
      NEXT_DIST_DIR: '.next-test',
      API_INTERNAL_URL: 'http://127.0.0.1:8102',
      NEXT_PUBLIC_APP_ENV: 'local',
      NEXT_PUBLIC_LOCAL_AUTH_BYPASS: 'false',
      NEXT_PUBLIC_FIREBASE_API_KEY: '',
      NEXT_PUBLIC_FIREBASE_PROJECT_ID: '',
      NEXT_PUBLIC_FIREBASE_APP_ID: '',
      NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: '',
    },
  },
})
