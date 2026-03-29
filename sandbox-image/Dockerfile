FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    curl git nodejs npm python3 python3-pip \
    ca-certificates iproute2 procps \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r sandbox && \
    useradd -r -g sandbox -d /sandbox -s /bin/bash sandbox && \
    mkdir -p /sandbox/.openclaw && \
    chown -R sandbox:sandbox /sandbox

USER sandbox
WORKDIR /sandbox
