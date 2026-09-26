# Builds the static app, then serves it from nginx, proxying `/api/v1` to `API_UPSTREAM` and
# writing `/config.json` from the [Runtime](/architecture/services/frontend.md#runtime) keys the
# client reads ([frontend Design](/architecture/services/frontend.md#design)).
#
# Built with the repository root as context (`docker build -f apps/web/Dockerfile .`), so the
# generated client can read the api's committed OpenAPI snapshot.

FROM node:22-slim AS builder

WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

COPY apps/web/. .
COPY apps/api/openapi.json /apps/api/openapi.json
RUN npx openapi-typescript /apps/api/openapi.json -o src/api/schema.gen.ts && npm run build

FROM nginx:1.27-alpine AS runtime

COPY apps/web/templates/default.conf.template /etc/nginx/templates/default.conf.template
COPY apps/web/templates/config.json.template /usr/share/nginx/html/config.json.template
COPY apps/web/docker/write-config-json.sh /docker-entrypoint.d/40-write-config-json.sh
COPY --from=builder /app/dist /usr/share/nginx/html

ENV API_UPSTREAM=http://api:8000
EXPOSE 80
