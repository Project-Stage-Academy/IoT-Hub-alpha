# Use the official Nginx image from Docker Hub
FROM nginx:alpine

# Remove the default configuration file that comes with the image
RUN rm /etc/nginx/conf.d/default.conf

# Copy your custom nginx.conf from your local machine
# into the location where Nginx in the container looks for configs
COPY nginx.conf /etc/nginx/conf.d/
