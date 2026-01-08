/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#e6f7ff',
          100: '#b3e6ff',
          200: '#80d4ff',
          300: '#4dc3ff',
          400: '#26b5ff',
          500: '#00a8ff',
          600: '#0099e6',
          700: '#007acc',
          800: '#005c99',
          900: '#003d66',
        },
        medical: {
          light: '#e8f5e9',
          DEFAULT: '#4caf50',
          dark: '#2e7d32',
        },
        emergency: {
          light: '#ffebee',
          DEFAULT: '#f44336',
          dark: '#c62828',
        }
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'glow': 'glow 2s ease-in-out infinite alternate',
      },
      keyframes: {
        glow: {
          '0%': { boxShadow: '0 0 5px rgba(0, 168, 255, 0.5)' },
          '100%': { boxShadow: '0 0 20px rgba(0, 168, 255, 0.8)' },
        }
      }
    },
  },
  plugins: [],
}
