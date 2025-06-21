
FROM ubuntu:24.04

RUN apt-get update && \
    apt-get install -y xfsprogs && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]