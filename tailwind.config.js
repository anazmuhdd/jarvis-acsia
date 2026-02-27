/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Segoe UI Variable"', '"Segoe UI"', 'Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
      },
      colors: {
        accent: {
          DEFAULT: '#1a73e8',
          light: '#e8f0fe',
          red: '#ea4335',
          green: '#34a853',
          yellow: '#fbbc04',
        },
        bg: {
          main: '#f4f4f5',
          white: '#ffffff',
          card: '#ffffff',
          sidebar: '#f8f9fa',
        },
      },
      borderRadius: {
        card: '12px',
        'card-lg': '16px',
      },
      boxShadow: {
        card: '0 1px 3px rgba(0,0,0,0.06)',
        'card-md': '0 2px 8px rgba(0,0,0,0.08)',
        'card-lg': '0 4px 16px rgba(0,0,0,0.1)',
        'card-hover': '0 6px 20px rgba(0,0,0,0.1)',
      },
    },
  },
  plugins: [],
}
