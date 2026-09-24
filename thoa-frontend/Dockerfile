FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy the rest of the app and build
COPY . .
RUN npm run build

# Production stage using Nginx
FROM nginx:alpine

# Copy built assets from builder
COPY --from=build /app/dist /usr/share/nginx/html

# Expose port 80 (internal to docker network)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
