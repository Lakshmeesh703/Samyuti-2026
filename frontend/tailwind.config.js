/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        saffron: '#ff8b2b',
        gold: '#ffc857',
        indigoDeep: '#1f2452',
        violetDeep: '#4f2f83',
        night: '#0a0d1f',
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(255,255,255,0.08), 0 10px 30px rgba(80, 31, 181, 0.35)',
        soft: '0 8px 24px rgba(0,0,0,0.22)',
      },
      fontFamily: {
        sans: ['Inter', 'Poppins', 'system-ui', 'sans-serif'],
        sanskrit: ['Noto Serif Devanagari', 'Tiro Devanagari Sanskrit', 'serif'],
      },
      keyframes: {
        pulseGlow: {
          '0%, 100%': { opacity: '0.7', transform: 'scale(1)' },
          '50%': { opacity: '1', transform: 'scale(1.04)' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        shimmer: {
          '0%': { transform: 'translateX(-120%)' },
          '100%': { transform: 'translateX(220%)' },
        },
        floatY: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        bars: {
          '0%, 100%': { transform: 'scaleY(0.35)' },
          '50%': { transform: 'scaleY(1)' },
        },
      },
      animation: {
        pulseGlow: 'pulseGlow 2.2s ease-in-out infinite',
        fadeUp: 'fadeUp 0.6s ease-out both',
        shimmer: 'shimmer 1.4s ease-in-out infinite',
        floatY: 'floatY 3.2s ease-in-out infinite',
        bars: 'bars 1.2s ease-in-out infinite',
      },
      backgroundImage: {
        aurora:
          'radial-gradient(circle at 10% 20%, rgba(255,139,43,0.22), transparent 40%), radial-gradient(circle at 90% 5%, rgba(123,79,255,0.24), transparent 35%), radial-gradient(circle at 50% 95%, rgba(255,200,87,0.16), transparent 45%)',
      },
    },
  },
  plugins: [],
}
