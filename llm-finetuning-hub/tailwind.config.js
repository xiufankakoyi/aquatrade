/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0a0a0a',
          surface: '#111111',
          border: '#1f1f1f',
          text: '#e5e5e5',
          'text-muted': '#a3a3a3',
        }
      }
    },
  },
  plugins: [],
}

