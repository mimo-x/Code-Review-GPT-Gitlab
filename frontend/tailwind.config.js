/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
    'node_modules/preline/dist/*.js',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // Apple-style neutral grays
        apple: {
          50: '#fafafa',
          100: '#f5f5f7',
          200: '#e8e8ed',
          300: '#d2d2d7',
          400: '#b0b0b5',
          500: '#86868b',
          600: '#6e6e73',
          700: '#515154',
          800: '#3a3a3c',
          900: '#1d1d1f',
        },
        // Apple accent blue
        'apple-blue': {
          50: '#e3f2fd',
          100: '#bbdefb',
          200: '#90caf9',
          300: '#64b5f6',
          400: '#42a5f5',
          500: '#007aff',
          600: '#0071e3',
          700: '#0062cc',
          800: '#0052a3',
          900: '#003d7a',
        }
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'SF Pro Text', 'Helvetica Neue', 'sans-serif'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      spacing: {
        '18': '4.5rem',
        '88': '22rem',
      },
      borderRadius: {
        '2xl': '1.25rem',
        '3xl': '1.75rem',
        '4xl': '2rem',
      },
      boxShadow: {
        'apple': '0 2px 16px 0 rgba(0, 0, 0, 0.08)',
        'apple-lg': '0 8px 32px 0 rgba(0, 0, 0, 0.12)',
        'apple-xl': '0 16px 48px 0 rgba(0, 0, 0, 0.16)',
      },
      backdropBlur: {
        'apple': '20px',
      },
    },
  },
  plugins: [
    require('preline/plugin'),
  ],
}
