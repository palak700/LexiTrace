/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#17201c',
        paper: '#f7f6f1',
        moss: '#607466',
        coral: '#c66b54',
        bluegray: '#5e7c8a',
        gold: '#c49a45'
      }
    }
  },
  plugins: []
};
