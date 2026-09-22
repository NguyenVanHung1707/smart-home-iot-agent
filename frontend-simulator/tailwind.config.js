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
          DEFAULT: '#4a7c59',
          hover: '#3d674a',
          light: '#e9f1ec',
          dark: '#30523a',
        },
        background: '#faf6f0',
        tertiary: {
          DEFAULT: '#705c30',
          light: '#f5efe0',
        },
        surface: {
          DEFAULT: '#ffffff',
          container: '#f0ece4',
          variant: '#e4e0d8',
        },
        outline: {
          DEFAULT: '#cec7ba',
          variant: '#e0dad0',
        },
        earth: {
          dark: '#2c3531',
          muted: '#637069',
          light: '#f7f4ee',
        }
      },
      fontFamily: {
        headline: ['Literata', 'serif'],
        body: ['Nunito Sans', 'sans-serif'],
      },
      boxShadow: {
        soft: '0 4px 20px rgba(46, 50, 48, 0.06)',
        'soft-lg': '0 8px 30px rgba(46, 50, 48, 0.1)',
        glow: '0 0 25px rgba(245, 197, 66, 0.45)',
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
      }
    },
  },
  plugins: [],
}
