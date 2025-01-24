FROM python:3.9.7

RUN groupadd --gid 10001 app && \
    useradd -g app --uid 10001 --shell /usr/sbin/nologin --create-home --home-dir /app app && \
    apt-get update && \
    apt-get install -y default-jdk && \
    apt-get clean

COPY ["pushapkscript", "/app/pushapkscript/"]
COPY ["configloader", "/app/configloader/"]
COPY ["docker.d", "/app/docker.d/"]

# Copy the version.json file if it's present
COPY ["version.jso[n]", "/app/"]

RUN chown -R app:app /app && \
    ln -s /app/docker.d/healthcheck /bin/healthcheck

WORKDIR /app
USER app

RUN python -m venv /app \
 && cd pushapkscript \
 && /app/bin/pip install -r requirements/base.txt \
 && /app/bin/pip install . \
 && python -m venv /app/configloader_venv \
 && cd /app/configloader \
 && /app/configloader_venv/bin/pip install -r requirements/base.txt \
 && /app/configloader_venv/bin/pip install . \
 && cd /app

CMD ["/app/docker.d/init.sh"]
