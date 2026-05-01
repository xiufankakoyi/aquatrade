import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'
import { createConnection } from 'net'

async function hasStockName(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const body = '{"page":1,"page_size":1}'
    const req = [
      'POST /api/screener/filter HTTP/1.1',
      'Host: 127.0.0.1',
      'Content-Type: application/json',
      `Content-Length: ${body.length}`,
      'Connection: close',
      '',
      body
    ].join('\r\n')

    const socket = createConnection({ port, host: '127.0.0.1', timeout: 2000 }, () => {
      socket.write(req, () => {})
    })

    let data = ''
    socket.setEncoding('utf8')
    socket.on('data', (chunk) => { data += chunk })
    socket.on('end', () => {
      socket.destroy()
      resolve(data.includes('"stock_name"'))
    })
    socket.on('error', () => resolve(false))
    socket.on('timeout', () => { socket.destroy(); resolve(false) })
  })
}

async function findAvailableProxyPort(startPort: number, maxRetries: number = 5): Promise<number> {
  for (let port = startPort; port < startPort + maxRetries; port++) {
    const ok = await hasStockName(port)
    if (ok) {
      return port
    }
  }
  console.warn(`[proxy] 端口 ${startPort}~${startPort + maxRetries - 1} 均不可用，强制使用 ${startPort}`)
  return startPort
}

export default defineConfig(async () => {
  const proxyPort = await findAvailableProxyPort(5000, 5)
  console.log(`[proxy] 目标后端端口: ${proxyPort}`)

  return {
    plugins: [vue()],
    resolve: {
      alias: {
        '@': resolve(__dirname, 'src')
      }
    },
    server: {
      port: 5173,
      strictPort: true,
      host: true,
      proxy: {
        '/api': {
          target: `http://localhost:${proxyPort}`,
          changeOrigin: true,
          secure: false,
        },
        '/socket.io': {
          target: `http://localhost:${proxyPort}`,
          changeOrigin: true,
          ws: true,
          configure: (proxy, _options) => {
            proxy.on('error', (err, _req, _res) => {
              console.log('proxy error', err);
            });
            proxy.on('proxyReq', (proxyReq, req, _res) => {
              console.log('Sending Request to the Target:', req.url);
            });
            proxy.on('proxyRes', (proxyRes, req, _res) => {
              console.log('Received Response from the Target:', proxyRes.statusCode, req.url);
            });
          },
        }
      }
    },
    optimizeDeps: {
      include: [
        'vue',
        'vue-router',
        'pinia',
        'axios',
        'ant-design-vue',
        'monaco-editor'
      ],
      force: false
    },
    build: {
      target: 'esnext',
      minify: 'esbuild'
    }
  }
})
