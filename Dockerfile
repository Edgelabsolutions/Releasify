FROM python:3.14-alpine

# Image metadata
LABEL org.opencontainers.image.title="Releasify"
LABEL org.opencontainers.image.description="Semantic versioning and release automation for GitLab and GitHub"
LABEL org.opencontainers.image.authors="Oleh Hordon"
LABEL org.opencontainers.image.source="https://github.com/edgelabsolutions/releasify"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.vendor="Edge Solutions Lab"

# Install git and openssh-client for git operations
RUN apk add --no-cache git openssh-client

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY release.py .
COPY config.yaml .
COPY entrypoint.sh /usr/local/bin/

# Make scripts executable
RUN chmod +x release.py /usr/local/bin/entrypoint.sh

# Set entrypoint
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
