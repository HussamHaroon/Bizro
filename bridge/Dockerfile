FROM node:22-slim
WORKDIR /bridge
COPY package.json package-lock.json ./
RUN npm install --omit=dev --no-audit --no-fund
COPY index.mjs ./
ENV AUTH_DIR=/bridge/auth
VOLUME /bridge/auth
EXPOSE 8090
CMD ["node", "index.mjs"]
