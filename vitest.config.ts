import path from 'node:path'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: { include: ['components/**/*.test.{ts,tsx}', 'lib/**/*.test.{ts,tsx}', 'hooks/**/*.test.{ts,tsx}'] },
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname) },
  },
})
