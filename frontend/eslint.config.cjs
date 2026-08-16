const { FlatCompat } = require('@eslint/eslintrc');
// The FlatCompat helper requires the ESLint "recommended" config object in newer versions.
const { configs: eslintJsConfigs } = require('@eslint/js');
const globals = require('globals');

// Use FlatCompat to import shareable configs (eslint:recommended, plugin configs, prettier)
const compat = new FlatCompat({
  baseDirectory: __dirname,
  recommendedConfig: eslintJsConfigs.recommended,
});

// Base config: put ignores and environment globals first so they apply project-wide
const baseConfig = {
  ignores: [
    'node_modules/**',
    'dist/**',
    'build/**',
    'coverage/**',
    'pnpm-lock.yaml',
    'package-lock.json',
    'yarn.lock',
    'eslint.config.cjs',
  ],

  languageOptions: {
    ecmaVersion: 2024,
    sourceType: 'module',
    // Merge common globals: browser and node so libs and build scripts are understood
    globals: Object.assign({}, globals.browser, globals.node),
  },
};

module.exports = [
  baseConfig,

  // Expand shareable configs into flat entries (keep after baseConfig)
  ...compat.extends('eslint:recommended', 'plugin:@typescript-eslint/recommended', 'prettier'),

  // Project-specific rules
  {
    languageOptions: {
      parser: require('@typescript-eslint/parser'),
    },
    rules: {
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['warn', { argsIgnorePattern: '^_' }],
    },
  },

  // Per-file overrides for Svelte files
  {
    files: ['*.svelte'],
    languageOptions: {
      parser: require('svelte-eslint-parser'),
      parserOptions: {
        parser: require('@typescript-eslint/parser'),
        extraFileExtensions: ['.svelte'],
      },
    },
    rules: {},
  },
];
