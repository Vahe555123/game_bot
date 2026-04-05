/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        body: ['Manrope', 'sans-serif'],
      },
      colors: {
        ink: '#07111f',
        mist: '#eff8ff',
        brand: {
          50: '#f1fbff',
          100: '#daf6ff',
          200: '#b7edff',
          300: '#7fdefe',
          400: '#3bcbfb',
          500: '#12b4f5',
          600: '#0492d1',
          700: '#0a75a9',
          800: '#105f89',
          900: '#124f72',
        },
      },
      boxShadow: {
        glow: '0 24px 70px rgba(18, 180, 245, 0.28)',
        card: '0 24px 48px rgba(3, 14, 31, 0.38)',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
        shine: {
          '0%': { transform: 'translateX(-160%) skewX(-18deg)' },
          '100%': { transform: 'translateX(240%) skewX(-18deg)' },
        },
      },
      animation: {
        float: 'float 6s ease-in-out infinite',
        shine: 'shine 2.2s linear infinite',
      },
    },
  },
  plugins: [],
}
