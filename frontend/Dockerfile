FROM node:22-slim AS build
WORKDIR /app
# next.config.ts reads BACKEND_URL when `next build` computes the rewrite
# rules, and freezes the result into the compiled output - it is NOT re-read
# when the container later starts. Render (and `docker build --build-arg`)
# only injects a service's environment variables at container *runtime* by
# default, so this ARG is required to get the real value in at build time too.
ARG BACKEND_URL
ENV BACKEND_URL=$BACKEND_URL
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "start"]
