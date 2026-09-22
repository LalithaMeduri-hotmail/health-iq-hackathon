# Health IQ SPA. `VITE_*` values are inlined at build time, so the API origin is a build ARG -
# setting it as a container env var at runtime would have no effect.
FROM node:20-alpine AS build

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_DEMO_MODE=false
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_DEMO_MODE=$VITE_DEMO_MODE

WORKDIR /srv/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /srv/frontend/dist /usr/share/nginx/html
EXPOSE 80
