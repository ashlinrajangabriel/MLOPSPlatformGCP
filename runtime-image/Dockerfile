# Use the official Jupyter minimal-notebook as base
FROM jupyter/minimal-notebook:latest

USER root

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    git \
    gnupg \
    jq \
    sudo \
    vim \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install code-server (VSCode)
RUN curl -fsSL https://code-server.dev/install.sh | sh

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install VSCode extensions
RUN code-server --install-extension ms-python.python \
    && code-server --install-extension ms-toolsai.jupyter \
    && code-server --install-extension ms-azuretools.vscode-docker \
    && code-server --install-extension eamodio.gitlens \
    && code-server --install-extension esbenp.prettier-vscode

# Configure code-server
COPY code-server-config.yaml /home/jovyan/.config/code-server/config.yaml
RUN chown -R jovyan:users /home/jovyan/.config

# Configure Jupyter
COPY jupyter_notebook_config.py /etc/jupyter/jupyter_notebook_config.py
RUN chown -R jovyan:users /etc/jupyter

# Switch back to jovyan user
USER jovyan

# Set up entry point script
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN sudo chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8888 8080

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
