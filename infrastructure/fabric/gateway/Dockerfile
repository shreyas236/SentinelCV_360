FROM node:24-bookworm-slim
WORKDIR /gateway
COPY package*.json ./
RUN npm ci --omit=dev
COPY server.mjs ./
USER node
EXPOSE 8770
CMD ["node","server.mjs"]
