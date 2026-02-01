FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    reprepro \
    gnupg \
    nginx \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /repo/apt /repo/conf /repo/auth

WORKDIR /repo

COPY conf /repo/conf
COPY auth /repo/auth

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
