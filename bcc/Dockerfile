FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# Install BCC tools and dependencies
RUN apt-get update && apt-get install -y \
    bpfcc-tools \
    python3-bpfcc \
    linux-headers-generic \
    linux-tools-generic \
    iproute2 \
    procps \
    file \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /scripts
