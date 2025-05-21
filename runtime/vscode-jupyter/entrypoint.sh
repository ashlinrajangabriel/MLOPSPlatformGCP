#!/bin/bash

# Initialize Git repository if not already initialized
if [ ! -d "${WORKSPACE_DIR}/.git" ]; then
    cd ${WORKSPACE_DIR}
    git init
    git config --global user.email "user@developer-platform.local"
    git config --global user.name "Developer Platform User"
    
    # Configure Git LFS
    git lfs install
    
    # Set up pre-commit hooks
    cp /etc/pre-commit-config.yaml .pre-commit-config.yaml
    pre-commit install
    
    # Configure nbdime for Jupyter notebook diffing
    nbdime config-git --enable --global
    
    # Create initial commit
    git add .
    git commit -m "Initial workspace setup" || true
fi

# Start code-server
exec /usr/bin/entrypoint.sh "$@" 