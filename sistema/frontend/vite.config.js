import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O sistema e publicado em https://DOMINIO/acesso, e nao na raiz do dominio.
export default defineConfig({
  base: "/acesso/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // Em desenvolvimento o Vite encaminha a API para o uvicorn. O prefixo
      // /acesso/api e removido aqui, tal como o nginx fara em producao.
      "/acesso/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (caminho) => caminho.replace(/^\/acesso\/api/, ""),
      },
    },
  },
});
