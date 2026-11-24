import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // 开发时把 /api 代理到后端，前端无需写死地址
      "/api": {
        target: "http://backend:9000",  // docker-compose 内
        changeOrigin: true,
      },
    },
  },
})
