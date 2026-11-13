import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Fixed isolated target: no development fallback or environment override.
export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [{
            debugName: 'react-runtime',
            name(id) {
              const normalized = id.replaceAll('\\', '/')
              return /\/node_modules\/(react|react-dom|scheduler)\//.test(normalized) ? 'react-runtime' : null
            },
          }],
        },
      },
    },
  },
  server: {
    host: '127.0.0.1', port: 5173, strictPort: true,
    proxy: { '/api': { target: 'http://127.0.0.1:8001', changeOrigin: false } },
  },
  preview: { host: '127.0.0.1', port: 4173, strictPort: true },
  test: {
    maxWorkers: 2,
    testTimeout: 15000,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
    restoreMocks: true,
  },
})
