import {defineConfig} from 'vite';
import tailwind from '@tailwindcss/vite';
import {resolve} from 'path';

export default defineConfig({
  root: resolve(__dirname),
  base: './',
  plugins: [tailwind()],
  build: {
    outDir: resolve(__dirname, '../ui'),
    emptyOutDir: true,
  },
});
