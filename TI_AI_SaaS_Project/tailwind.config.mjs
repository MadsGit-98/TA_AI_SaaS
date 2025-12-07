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
        'primary-bg': '#0E1015',           // Deep Charcoal - Base dark mode background
        'primary-text': '#FFFFFF',        // Pure White - High contrast main text
        'secondary-text': '#A0A0A0',      // Medium Grey - Subtle metadata/supporting text
        'accent-cta': '#00FFC0',          // Vibrant Cyan/Teal - Primary call-to-action/link color
        'code-block-bg': '#1C1F26',       // Subtle Dark Grey - Code and card background
      },
      accentColor: {
        'cta': '#00FFC0',
      }
    },
  },
  plugins: [],
}