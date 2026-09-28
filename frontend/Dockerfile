# ============================================================================
# TRILOK TRACE — Frontend Dockerfile
# Multi-stage: build (node) → serve (nginx)
# ============================================================================

# --- Build stage --------------------------------------------------------------
FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --prefer-offline

COPY . .
RUN npm run build

# --- Serve stage (nginx) ------------------------------------------------------
FROM nginx:alpine AS prod

# Remove default nginx config
RUN rm /etc/nginx/conf.d/default.conf

# Custom nginx config: serve SPA + proxy /api to backend
COPY nginx.conf /etc/nginx/conf.d/trilok-trace.conf

# Copy built assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
