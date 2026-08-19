FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./
COPY vendor/xlsx-0.20.3.tgz vendor/xlsx-0.20.3.tgz
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine

COPY docker/nginx/default.conf /etc/nginx/conf.d/default.conf
COPY docker/nginx/40-runtime-config.sh /docker-entrypoint.d/40-runtime-config.sh
COPY --from=build /app/dist /usr/share/nginx/html
RUN sed -i 's/\r$//' /docker-entrypoint.d/40-runtime-config.sh \
  && chmod +x /docker-entrypoint.d/40-runtime-config.sh

EXPOSE 80
