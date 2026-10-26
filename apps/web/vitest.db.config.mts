import { defineConfig } from "vitest/config";
import tsconfigPaths from "vite-tsconfig-paths";

// Database tests need the local Supabase stack (make db-start); run with `pnpm test:db`.
export default defineConfig({
  plugins: [tsconfigPaths()],
  test: {
    environment: "node",
    include: ["src/**/*.db.test.ts"],
    fileParallelism: false,
  },
});
