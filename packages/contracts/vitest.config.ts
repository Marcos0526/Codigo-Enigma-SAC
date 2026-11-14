import { defineConfig } from 'vitest/config';
import path from 'path';

export default defineConfig({
  test: {
    environment: 'node',
    include: ['tests/**/*.test.ts'],
    globals: true,
    alias: {
      '@enigma-sac/contracts': path.resolve(__dirname, './dist/index.js'),
    },
  },
});