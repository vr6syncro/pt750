FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

RUN apt-get update && apt-get install --no-install-recommends -y \
    ghostscript \
    libsnmp-dev \
    libudev-dev \
    libsnmp-base \
    libgl1 \
    curl \
    libglib2.0-0 \
    libgthread-2.0-0 \
    libgtk-3-0 \
    libgstreamer1.0-0 \
    libgstreamer-plugins-base1.0-0 \
    fonts-dejavu-core \
    fonts-liberation \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN pip install poetry==1.8.3

RUN poetry config virtualenvs.create false
COPY ./pyproject.toml ./poetry.lock /app/

RUN poetry install --only=main --no-root

COPY . /app

RUN adduser --disabled-password --gecos '' appuser \
    && chown -R appuser:appuser /app \
    && mkdir -p /app/custom_fonts \
    && chown -R appuser:appuser /app/custom_fonts
USER appuser

ENTRYPOINT ["/app/docker/docker-entrypoint.sh"]
CMD ["labels"]
