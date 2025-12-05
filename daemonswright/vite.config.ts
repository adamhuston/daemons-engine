import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  root: path.resolve(__dirname, 'src'),
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@renderer': path.resolve(__dirname, './src/renderer'),
      '@main': path.resolve(__dirname, './src/main'),
      '@shared': path.resolve(__dirname, './src/shared'),
    },
  },
  base: './',
  build: {
    // When root is src/, output to project-level dist/renderer
    outDir: path.resolve(__dirname, 'dist', 'renderer'),
    emptyOutDir: true,
    // Enable sourcemaps and keep output readable for easier debugging of built artifacts
    sourcemap: true,
    // Disable minification for debug builds (set to 'esbuild' or 'terser' for production)
    minify: false,
  },
});
