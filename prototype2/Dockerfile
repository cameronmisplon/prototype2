FROM ubuntu:20.10 AS base
RUN apt update -y
FROM base AS builder
RUN apt -y install clang-11 lldb-11 lld-11
RUN apt -y install clang git
RUN apt update -y
RUN git clone https://github.com/JBontes/CarlSAT_2021
RUN git clone https://github.com/marijnheule/rnd-route
RUN git clone https://oauth2:bRgUGkaEAXpgvecFHLqj@gitlab.cs.uct.ac.za/capstoneproject16/capstone
RUN apt -y install make
RUN cd CarlSAT_2021; \
    make clean && make
FROM base as exec
COPY --from=builder /CarlSAT_2021/CarlSAT .
COPY --from=builder /rnd-route/tests .
COPY --from=builder /capstone .
RUN mkdir /mnt/ramdisk
RUN apt -y install python3 vim
RUN apt-get -y install mysql-server
RUN apt-get -y install python3-pip
RUN apt update -y
RUN pip3 install -Ur ./prototype1/requirements.txt
CMD python3 prototype2/prototype2.py

