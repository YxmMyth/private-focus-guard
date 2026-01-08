import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import electron from 'vite-plugin-electron';
import path from 'path';

// https://vitejs.dev/config/
export default defineConfig({
  // 添加环境变量定义
  define: {
    'process.env.VITE_DEV_SERVER_URL': JSON.stringify('http://localhost:5173')
  },
  plugins: [
    react(),
    electron([
      {
        // Main process entry point
        entry: 'src/main/index.ts',
        vite: {
          build: {
            outDir: 'dist/main',
            rollupOptions: {
              external: ['electron', 'active-win', 'better-sqlite3', '@tencentcloud/hunyuan-sdk-nodejs', 'iconv', 'node-gyp-build', 'sql.js']
            }
          }
        }
      },
      {
        // Preload script entry point
        entry: 'src/preload/index.ts',
        onstart(args) {
          // Preload 脚本更改时通知渲染进程重新加载
          args.reload();
        },
        vite: {
          build: {
            outDir: 'dist/preload',
            rollupOptions: {
              external: ['electron', 'active-win', 'better-sqlite3', '@tencentcloud/hunyuan-sdk-nodejs', 'iconv', 'node-gyp-build']
            }
          }
        }
      }
    ])
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@domain': path.resolve(__dirname, './src/domain'),
      '@main': path.resolve(__dirname, './src/main'),
      '@services': path.resolve(__dirname, './src/services'),
      '@storage': path.resolve(__dirname, './src/storage'),
      '@renderer': path.resolve(__dirname, './src/renderer')
    }
  },
  server: {
    port: 5173
  }
});
