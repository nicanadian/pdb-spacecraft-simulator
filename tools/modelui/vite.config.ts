import { defineConfig } from 'vite';
import solidPlugin from 'vite-plugin-solid';

export default defineConfig({
  plugins: [solidPlugin()],
  base: './',
  build: {
    outDir: 'dist',
    target: 'esnext',
  },
  server: {
    port: 8090,
    open: true,
  },
});
