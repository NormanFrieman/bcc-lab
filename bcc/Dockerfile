FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install BCC tools and dependencies. linux-headers-generic ensures headers
# are present for the running kernel version via the mounted /usr/src volume.
RUN apt-get update && apt-get install -y \
    bpfcc-tools \
    python3-bpfcc \
    linux-headers-generic \
    iproute2 \
    procps \
    file \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /scripts
