import js from "@eslint/js";
import jsxA11y from "eslint-plugin-jsx-a11y";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist", "coverage", "src/api/schema.gen.ts"] },
  js.configs.recommended,
  {
    files: ["src/**/*.{ts,tsx}", "vite.config.ts"],
    extends: [...tseslint.configs.strictTypeChecked, jsxA11y.flatConfigs.recommended],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_" }],
      "no-warning-comments": ["error", { terms: ["PLACEHOLDER"], location: "start" }],
    },
  },
  {
    files: ["src/mocks/**/*.{ts,tsx}"],
    rules: { "no-warning-comments": "off" },
  },
  {
    files: ["src/**/*.test.{ts,tsx}", "src/setupTests.ts"],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
  },
  {
    files: ["*.config.{js,ts}"],
    languageOptions: {
      globals: globals.node,
    },
  },
);
