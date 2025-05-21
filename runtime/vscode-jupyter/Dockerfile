FROM codercom/code-server:latest

# Install Python and Jupyter
RUN sudo apt-get update && \
    sudo apt-get install -y python3-pip git && \
    pip3 install jupyter jupyterlab

# Install Git and versioning tools
RUN sudo apt-get install -y git git-lfs && \
    pip3 install nbdime pre-commit

# Configure Git for automatic versioning
COPY git-init.sh /usr/local/bin/
COPY pre-commit-config.yaml /etc/pre-commit-config.yaml
RUN chmod +x /usr/local/bin/git-init.sh

# Set up workspace initialization
ENV WORKSPACE_DIR=/home/coder/workspace
RUN mkdir -p ${WORKSPACE_DIR}

# Initialize Git repo on workspace mount
COPY entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"] 