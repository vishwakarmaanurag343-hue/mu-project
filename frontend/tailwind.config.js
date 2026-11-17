/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#0a0e17',
          surface: '#111726',
          card: '#161f33',
          border: 'rgba(255, 255, 255, 0.08)',
          glow: '#1e2d4d',
        },
        accent: {
          blue: '#2563eb',
          cyan: '#06b6d4',
          emerald: '#10b981',
          rose: '#f43f5e',
        },
      },
      boxShadow: {
        'glow-blue': '0 0 25px -5px rgba(37, 99, 235, 0.35)',
        'glow-cyan': '0 0 25px -5px rgba(6, 182, 212, 0.35)',
        'glow-card': '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      },
    },
  },
  plugins: [],
};

