FROM node:20-alpine AS base
RUN apk add --no-cache chromium nss freetype harfbuzz ca-certificates ttf-freefont udev
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium-browser
ENV BROWSER_HEADLESS=true
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
RUN mkdir -p /tmp/cargoiq-screenshots && chown appuser:appgroup /tmp/cargoiq-screenshots
USER appuser
CMD ["node", "dist/index.js"]
