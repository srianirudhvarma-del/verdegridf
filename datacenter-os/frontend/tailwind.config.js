/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: 'var(--bg-color)',
        card: 'var(--card-bg)',
        borderC: 'var(--border-color)',
        sidebar: 'var(--sidebar-bg)',
        textMain: 'var(--text-main)',
        textMuted: 'var(--text-muted)',
        accent: {
          green: 'var(--accent-green)',
          gold: 'var(--accent-gold)',
          red: 'var(--accent-red)',
          orange: 'var(--accent-gold)', 
          violet: 'var(--accent-violet)',
          cyan: 'var(--accent-cyan)',
          ghost: 'var(--border-color)'
        }
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'sans-serif'],
        mono: ['IBM Plex Mono', 'monospace'],
        metric: ['Doto', 'Orbitron', 'monospace'],
      },
      animation: {
        'breath': 'breath 10s ease-in-out infinite',
        'pulse-fast': 'pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      },
      keyframes: {
        breath: {
          '0%, 100%': { opacity: '0.8' },
          '50%': { opacity: '1' },
        }
      }
    },
  },
  plugins: [],
}
