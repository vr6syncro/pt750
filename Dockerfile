FROM ghcr.io/astral-sh/uv:python3.10-bookworm

RUN groupadd --system --gid 999 nonroot && \
    useradd --system --gid 999 --uid 999 --create-home nonroot

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UVLINK_MODE=copy
ENV UV_NO_DEV=1
ENV UV_TOOL_BIN_DIR=/usr/local/bin

RUN sed -i /etc/apt/sources.list -e 's/ main/ main contrib non-free/' || /bin/true
RUN sed -i /etc/apt/sources.list.d/debian.sources -e 's/Components: main/Components: main contrib non-free/' || /bin/true
RUN apt-get update && apt-get install --no-install-recommends -y \
    ghostscript \
    libsnmp-dev \
    libudev-dev \
    libsnmp-base \
    snmp-mibs-downloader \
    libgl1 \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/*

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.git,target=.git \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project

COPY --exclude=**/.git . /app

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["/app/docker/docker-entrypoint.sh"]
USER nonroot

CMD ["labels"]
