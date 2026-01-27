FROM docker:26.1-dind

ENV DOCKER_TLS_CERTDIR=""

RUN apk add --no-cache docker-cli-compose

WORKDIR /demo

COPY demo-compose.yml /demo/demo-compose.yml
COPY run-demo.sh /demo/run-demo.sh

RUN chmod +x /demo/run-demo.sh

ENTRYPOINT ["/demo/run-demo.sh"]
