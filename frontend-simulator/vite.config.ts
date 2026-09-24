import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';
import path from 'path';

const realRoot = fs.realpathSync(process.cwd());

export default defineConfig({
  root: realRoot,
  base: './',
  plugins: [react()],
  build: {
    outDir: path.resolve(realRoot, 'dist'),
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true,
      },
    },
  },
});
