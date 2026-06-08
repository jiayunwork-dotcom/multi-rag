FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
COPY .npmrc ./
RUN npm install --no-audit --no-fund

COPY . .
RUN npm run build

FROM nginx:alpine

COPY nginx.conf /etc/nginx/nginx.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
