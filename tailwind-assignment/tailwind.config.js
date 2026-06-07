/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/**/*.html'], //this means scan every .html file in the src folder and its subfolders for class names
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        'background': '#FFF7FA',
        'surface': '#FFFFFF', 
        'primary': '#E879A6',
        'dark-background': '#111018',
        'dark-surface': '#1A1824',
        'dark-primary': '#B794F4',
      },
    },
  },
  plugins: [],
}