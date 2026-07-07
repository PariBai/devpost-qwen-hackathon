# Hikmat PSX frontend — multi-stage: build the Vite bundle, then serve it with nginx.
#
# The bundle is built with VITE_API_BASE="/" so the app calls the API same-origin
# (nginx reverse-proxies /auth, /chats, /me, /health to the backend). One clean URL,
# no CORS, no backend IP baked into the JS.

# ---------- build stage ----------
FROM node:20-alpine AS build

WORKDIR /app

# Install deps first (own layer) for build caching.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Same-origin API base (stripped to "" at runtime -> requests hit the current host).
ARG VITE_API_BASE="/"
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ---------- serve stage ----------
FROM nginx:1.27-alpine

# SPA-aware config (history fallback) + API reverse proxy.
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
