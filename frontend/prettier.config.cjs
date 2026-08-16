module.exports = {
  // Basic formatting rules
  printWidth: 100,
  tabWidth: 2,
  useTabs: false,
  semi: true,
  singleQuote: true,
  trailingComma: 'es5',
  bracketSpacing: true,
  arrowParens: 'always',
  // Use the Svelte plugin when available
  plugins: [require.resolve('prettier-plugin-svelte')],
  // Svelte-specific options
  svelteSortOrder: 'scripts-styles-markup-options',
  svelteStrictMode: false,
  svelteAllowShorthand: true,
};
