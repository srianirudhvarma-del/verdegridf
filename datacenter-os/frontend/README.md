# GreenCore - Smart Infrastructure Dashboard

A React-based dashboard for real-time datacenter sustainability monitoring and optimization, featuring the "Obsidian Gold" design system.

## 🚀 Modules

- **Overview**: Bento-grid dashboard with unified efficiency metrics
- **IDLEhunter**: Server consolidation with real-time idle detection
- **WaterWatch**: Water usage efficiency monitoring and benchmarking
- **CarbonClock**: Carbon-aware job scheduling with 24h intensity forecasting
- **ThermalTrace**: 8×8 thermal grid with hotspot detection and prediction
- **LightSpeed**: Network topology visualization with traffic optimization

Plus two setup/onboarding flows outside the main dashboard:
- **Onboarding**: First-run facility profile setup (stored in `localStorage`)
- **Deployment Plan** / **Hardware Setup**: Guided hardware rollout reference

A floating AI assistant (`AIAgent`) is available on every dashboard page, grounded in that module's live data and the facility profile.

## 🎨 Design System

- **Background**: Deep Navy/Black (#05070A)
- **Cards**: #0F1218 with backdrop blur
- **Accents**: Gold (#FFD700), Neon Teal (#00F2FF)
- **Typography**: Inter/Geist Sans + JetBrains Mono
- **Animations**: Framer Motion with global pulse effects

## 🛠 Tech Stack

- **Frontend**: React 18 + Vite
- **Styling**: Tailwind CSS + clsx/tailwind-merge
- **Charts**: Recharts + D3.js
- **Animations**: Framer Motion
- **API**: The dashboard runs entirely on deterministic local mock/simulation data (`src/data/mock/`) — there is currently no live connection to the FastAPI backend below

Note: there is no client-side router — navigation is plain React state (`activeTab` in `App.jsx`), not `react-router-dom`.

## 📦 Installation

```bash
cd datacenter-os/frontend
npm install
```

## 🚀 Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

## 🏗 Backend

A separate FastAPI backend lives in `datacenter-os/backend/` and exposes the same shape of data (idlehunter, waterwatch, carbonclock, thermaltrace, lightspeed). It is **not currently called by this frontend** — every module here runs on its own local mock generator instead. The backend can be run and tested independently:

```bash
cd datacenter-os/backend
pip install -r requirements.txt
python main.py
```

Wiring the frontend to this backend (replacing `src/data/mock/*` calls with real HTTP requests) is a deliberate future step, not yet done.

## 🔑 Environment Variables

- `VITE_DEEPSEEK_API_KEY` — API key for the floating AI assistant (`AIAgent`); the assistant degrades gracefully without one

## 📁 Project Structure

```
src/
├── components/
│   └── shared/          # Navigation, AIAgent, MetricCard, HeatmapGrid, etc.
├── context/
│   └── MetricsContext.jsx
├── data/
│   ├── mock/             # Deterministic mock data generators used across modules
│   └── *.json             # Static seed data
├── logic/
│   └── configurator.js
├── modules/               # One folder per dashboard module (idlehunter, waterwatch,
│                           # carbonclock, thermaltrace, lightspeed, overview) — each is
│                           # the live implementation shown in the app
├── pages/
│   ├── Onboarding.jsx
│   ├── DeploymentPlan.jsx
│   └── HardwareGuide.jsx
├── lib/
│   └── utils.js
├── App.jsx
└── main.jsx
```

## 🎯 Key Features

- **Real-time Updates**: 3-5 second refresh cycles
- **Responsive Design**: Mobile-first approach
- **Smooth Animations**: Page transitions and interactive elements
- **Accessibility**: Keyboard navigation and screen reader support
- **Performance**: Optimized rendering with React.memo and useMemo

## 🔧 Customization

The design system is fully customizable through Tailwind config. Colors, fonts, and spacing can be adjusted in `tailwind.config.js`.

## 📄 License

This project is part of the GreenCore datacenter optimization suite.
