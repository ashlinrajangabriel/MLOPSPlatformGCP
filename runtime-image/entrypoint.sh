#!/bin/bash

# Start code-server in background
code-server --bind-addr 0.0.0.0:8080 --auth none &

# Start Jupyter server
exec jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --NotebookApp.token='' --NotebookApp.password='' 