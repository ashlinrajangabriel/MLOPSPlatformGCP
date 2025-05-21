#!/bin/bash
set -e

# Default values
CONFIG_FILE=""
MODE="sync"
NUM_WORKERS=1
PORT=8000

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        train)
            COMMAND="train"
            shift
            ;;
        serve)
            COMMAND="serve"
            shift
            ;;
        process)
            COMMAND="process"
            shift
            ;;
        --config)
            CONFIG_FILE="$2"
            shift
            shift
            ;;
        --mode)
            MODE="$2"
            shift
            shift
            ;;
        --workers)
            NUM_WORKERS="$2"
            shift
            shift
            ;;
        --port)
            PORT="$2"
            shift
            shift
            ;;
        --help)
            echo "Usage: entrypoint.sh [train|serve|process] [options]"
            echo ""
            echo "Commands:"
            echo "  train               Run training job"
            echo "  serve               Start inference service"
            echo "  process             Run data processing"
            echo ""
            echo "Options:"
            echo "  --config FILE       Configuration file"
            echo "  --mode MODE         Serving mode (sync|async|batch)"
            echo "  --workers N         Number of workers"
            echo "  --port N            Port number for serving"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate config file
if [[ -z "$CONFIG_FILE" ]]; then
    echo "Error: --config is required"
    exit 1
fi

# Execute command
case $COMMAND in
    train)
        echo "Starting training job..."
        python -m training.train --config "$CONFIG_FILE"
        ;;
    serve)
        echo "Starting inference service in $MODE mode..."
        case $MODE in
            sync)
                cd inference/sync
                gunicorn --workers $NUM_WORKERS --bind 0.0.0.0:$PORT app:app
                ;;
            async)
                cd inference/async
                uvicorn app:app --host 0.0.0.0 --port $PORT --workers $NUM_WORKERS
                ;;
            batch)
                cd inference/batch
                python batch_inference.py --config "$CONFIG_FILE"
                ;;
            *)
                echo "Invalid mode: $MODE"
                exit 1
                ;;
        esac
        ;;
    process)
        echo "Running data processing..."
        python -m preprocessing.preprocess --config "$CONFIG_FILE"
        ;;
    *)
        echo "Please specify a command: train, serve, or process"
        exit 1
        ;;
esac 