import { FlatCompat } from '@eslint/eslintrc'
const compat = new FlatCompat({ baseDirectory: import.meta.dirname })
export default [
  { ignores: ['.next/**', '.next-test/**', '.local/**', 'node_modules/**', 'backend/**', 'public/pdf-worker.min.mjs', 'next-env.d.ts', 'test-results/**', 'playwright-report/**'] },
  ...compat.extends('next/core-web-vitals', 'next/typescript'),
  { files: ['**/*.{ts,tsx}'], rules: { '@typescript-eslint/no-explicit-any': 'warn', '@typescript-eslint/no-unused-vars': 'warn', 'prefer-const': 'warn' } },
  { files: ['tailwind.config.js'], rules: { '@typescript-eslint/no-require-imports': 'off' } },
]
