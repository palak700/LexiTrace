FROM node:22-alpine

WORKDIR /app/frontend
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
CMD ["npm", "run", "dev"]
