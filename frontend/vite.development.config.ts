import { mergeConfig } from 'vite'
import isolatedConfig from './vite.config.ts'

// Explicit local development target; the isolated/test configuration stays unchanged.
export default mergeConfig(isolatedConfig, {
  server: {
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
})
