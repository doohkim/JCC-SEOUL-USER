# syntax = docker/dockerfile:experimental
FROM        python:3.13
ENV         LANG C.UTF-8
ENV         TZ Asia/Seoul
RUN         ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN         apt -y update &&\
            apt -y dist-upgrade &&\
            # manage.py compilemessages
            apt -y install gettext && \
            # python-magic
            apt -y install libmagic1 && \
            apt -y install libnginx-mod-http-geoip && \
            apt -y install geoip-database && \
            apt -y autoremove

            # psycopg2-binary (libpq M1 issue) \
RUN         apt -y install gcc libpq-dev && \
            pip install psycopg2-binary --no-binary psycopg2-binary && \
            apt -y autoremove


            # block reinstall psycopg2-binary
COPY        requirements.txt /tmp/requirements.tmp
RUN         awk '!/^psycopg2-binary==/' /tmp/requirements.tmp > /tmp/requirements.txt
RUN         --mount=type=cache,target=/root/.cache/pip \
            pip install -r /tmp/requirements.txt


RUN         mkdir /var/log/gunicorn

COPY        .   /srv/
WORKDIR     /srv/app

EXPOSE      8000
CMD         python manage.py shell_plus
