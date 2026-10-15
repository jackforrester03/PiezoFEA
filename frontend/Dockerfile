# Production frontend for server deployment: build the Vite app, serve it with nginx,
# and forward /api to the backend service. Local development still uses `npm run dev`.
FROM node:22-bookworm-slim AS build
WORKDIR /src
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /src/dist /usr/share/nginx/html
