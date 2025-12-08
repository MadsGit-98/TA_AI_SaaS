/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './templates/**/*.html',
    './apps/**/templates/**/*.html',
    './apps/**/static/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        'primary-bg': '#FFFFFF',           // Pure White - Base light mode background
        'primary-text': '#000000',       // Black - High contrast main text
        'secondary-text': '#A0A0A0',      // Medium Grey - Subtle metadata/supporting text
        'accent-cta': '#080707',          // Near Black - Primary call-to-action/link color
        'code-block-bg': '#E0E0E0',       // Light Grey - Code and card background
        'cta-text': '#FFFFFF',
      },
      accentColor: {
        'cta': '#080707',
      }
    },
  },
  plugins: [],
}