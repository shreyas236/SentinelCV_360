FROM node:24-bookworm-slim
WORKDIR /chaincode
COPY package*.json ./
RUN npm ci --omit=dev
COPY *.cjs ./
USER node
ENV CHAINCODE_SERVER_ADDRESS=0.0.0.0:9999
EXPOSE 9999
CMD ["npm","start"]
