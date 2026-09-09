import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    globals: true,
    include: ["src/**/__tests__/**/*.test.ts"],
    coverage: {
      provider: "v8",
      // "lcov" is required for sonar.javascript.lcov.reportPaths in
      // sonar-project.properties to find anything -- Vitest's v8 provider
      // does not include it by default, so coverage silently never reached
      // SonarQube even though the tests themselves ran fine.
      reporter: ["text", "lcov"],
      reportsDirectory: "coverage",
      exclude: ["src/**/__tests__/**"],
    },
  },
});

