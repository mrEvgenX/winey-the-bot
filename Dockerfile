FROM phusion/baseimage:focal-1.0.0-alpha1-amd64

RUN apt-get -y update && \
    apt-get install -qy postgresql-client python3 python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    pip3 install --upgrade pip

RUN mkdir /winey
WORKDIR /winey

COPY ./requirements.txt /winey/

RUN pip3 install -r /winey/requirements.txt

COPY ./winey /winey/winey
COPY runit/bot /etc/service/bot
COPY runit/webapp /etc/service/webapp
