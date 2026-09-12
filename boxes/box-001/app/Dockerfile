FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssh-client \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 appuser \
    && mkdir -p /opt/deploy /app/data

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py /app/app.py
COPY data/inventory.txt /app/data/inventory.txt
COPY config/deploy.conf /opt/deploy/deploy.conf
COPY config/id_rsa /opt/deploy/id_rsa

RUN chown -R appuser:appuser /app /opt/deploy \
    && chmod 400 /opt/deploy/id_rsa \
    && chmod 440 /opt/deploy/deploy.conf

USER appuser
ENV PYTHONUNBUFFERED=1
EXPOSE 5000
CMD ["python", "app.py"]
