# Nginx Dockerfile (optional - using official image in docker-compose)
# This file is kept for reference but docker-compose.prod.yml uses nginx:alpine

FROM nginx:alpine

# Copy custom configuration
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

# Create necessary directories
RUN mkdir -p /var/www/certbot /etc/nginx/ssl /var/log/nginx

# Expose ports
EXPOSE 80 443

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

