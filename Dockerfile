FROM python:3.11-slim-bookworm

# System deps:
# - pandoc for markdown->docx
# - node/npm for mermaid-cli
# - chromium deps for puppeteer (mermaid-cli)
RUN apt-get update && apt-get install -y --no-install-recommends \
    pandoc \
    nodejs \
    npm \
    ca-certificates \
    fonts-dejavu-core \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libxshmfence1 \
    libxss1 \
    libxkbcommon0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install mermaid-cli globally (provides mmdc)
RUN npm i -g @mermaid-js/mermaid-cli

# Install md2docx
WORKDIR /opt/md2docx
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Puppeteer config + wrapper so md2docx can render mermaid reliably
COPY docker/puppeteer-config.json /etc/md2docx/puppeteer-config.json
COPY docker/mmdc-wrapper.sh /usr/local/bin/md2docx-mmdc
RUN chmod +x /usr/local/bin/md2docx-mmdc

# Make md2docx use our wrapper as the first candidate
ENV MD2DOCX_MMDC=md2docx-mmdc

# Default workdir will be a mounted volume
WORKDIR /work
ENTRYPOINT ["md2docx"]
