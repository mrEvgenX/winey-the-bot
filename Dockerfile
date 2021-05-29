FROM phusion/baseimage:focal-1.0.0-alpha1-amd64

RUN apt-get -y update && \
    apt-get install -qy postgresql-client python3 python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    pip3 install --upgrade pip

RUN mkdir /wine_log
WORKDIR /wine_log

COPY ./requirements.txt /wine_log/

RUN pip3 install -r /wine_log/requirements.txt

COPY ./wine_log /wine_log/wine_log
COPY runit/bot /etc/service/bot
COPY runit/webapp /etc/service/webapp
