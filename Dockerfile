FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "mcp>=2,<3" "uv>=0.8,<1"

ARG NATURAL_JAPANESE_COMMIT=9a78a42964096da509b8f3e011f0085a5f080151
RUN git clone https://github.com/coji/natural-japanese.git /opt/natural-japanese \
    && cd /opt/natural-japanese \
    && git checkout "$NATURAL_JAPANESE_COMMIT" \
    && rm -rf .git

RUN uv run /opt/natural-japanese/skills/natural-japanese/scripts/lint.py --help >/dev/null

WORKDIR /app
COPY server.py /app/server.py

EXPOSE 8000

CMD ["python", "server.py"]
