# ---------- STAGE 1: Build the Web Flasher ----------
FROM node:20-alpine AS builder

RUN apk add --no-cache git curl bash

# Install pnpm
ENV PNPM_HOME="/root/.local/share/pnpm"
ENV PATH="${PNPM_HOME}:${PATH}"
RUN curl -fsSL https://get.pnpm.io/install.sh | SHELL=bash sh -

# Clone web-flasher (defcon-33)
WORKDIR /build
RUN git clone --branch defcon-33 --depth=1 https://github.com/meshtastic/web-flasher.git

WORKDIR /build/web-flasher

# Patch the firmware URL to use local files
RUN sed -i 's|https://raw.githubusercontent.com/meshtastic/meshtastic.github.io/master|http://localhost|g' composables/api.ts

# Install and build
RUN pnpm install && pnpm run build

# ---------- STAGE 2: Serve via Nginx ----------
FROM nginx:alpine

# Clone meshtastic.github.io for firmware files
WORKDIR /tmp
RUN apk add --no-cache git && \
    git clone --depth=1 https://github.com/meshtastic/meshtastic.github.io.git

# Copy flasher UI
COPY --from=builder /build/web-flasher/.output/public /usr/share/nginx/html

# Copy firmware files (only the needed DEFCON folder)
RUN mkdir -p /usr/share/nginx/html/event && \
    cp -r /tmp/meshtastic.github.io/event/defcon33 /usr/share/nginx/html/event/defcon33

# Clean up git clone to reduce image size
RUN rm -rf /tmp/meshtastic.github.io

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
