# Hikmat PSX — Frontend

React (Vite) frontend for the PSX MemoryAgent. Currently implements the **welcome**,
**sign-up**, and **login** screens; the full chat experience is the next build step.

## Stack
- React 18 + Vite
- React Router (welcome / login / signup / chat)
- Plain CSS with design tokens (`src/styles/tokens.css`) matching the PSX design handoff

## Structure
```
src/
  api/           # fetch wrapper + auth endpoints
  components/    # BrandPanel, AuthLayout, Field, icons, ProtectedRoute
  context/       # AuthContext (token + user, persisted to localStorage)
  pages/         # Welcome, Login, Signup, Chat
  styles/        # tokens.css (design system) + auth.css (auth screens)
```

## Run locally
```bash
cd frontend
cp .env.example .env      # set VITE_API_BASE to your backend
npm install
npm run dev               # http://localhost:5173
```

`VITE_API_BASE` points at the FastAPI backend — `http://localhost:8086` for a local
backend, or the ECS IP (`http://47.84.234.2:8086`) for the deployed one.

## Build
```bash
npm run build             # outputs to dist/
npm run preview           # preview the production build
```
