import os
import yaml
import torch
from flask import Flask, request, jsonify
import mlflow
from typing import List, Dict, Any
import time

# Load configuration
with open("/config/inference.yaml") as f:
    config = yaml.safe_load(f)

# Initialize Flask app
app = Flask(__name__)

# Global model cache
model_cache = {}

def load_model(model_version: str = "latest"):
    """Load model from MLflow."""
    if model_version in model_cache:
        return model_cache[model_version]
    
    try:
        # Set MLflow tracking URI
        mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
        
        # Load model
        if model_version == "latest":
            model_uri = f"models:/{config['model']['name']}/latest"
        else:
            model_uri = f"models:/{config['model']['name']}/{model_version}"
        
        model = mlflow.pytorch.load_model(model_uri)
        
        # Move model to device
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = model.to(device)
        model.eval()
        
        model_cache[model_version] = model
        return model
    
    except Exception as e:
        raise Exception(f"Error loading model: {str(e)}")

def preprocess_input(data: List[Dict[str, Any]]):
    """Preprocess input data."""
    # Implement preprocessing logic here
    # This is a placeholder that returns the data as is
    return data

def postprocess_output(predictions: torch.Tensor):
    """Postprocess model output."""
    # Implement postprocessing logic here
    # This is a placeholder that converts tensor to list
    return predictions.tolist()

@app.route("/predict", methods=["POST"])
def predict():
    """Endpoint for model predictions."""
    start_time = time.time()
    
    try:
        # Parse request
        request_data = request.get_json()
        model_version = request_data.get("model_version", "latest")
        inputs = request_data["inputs"]
        
        # Load model
        model = load_model(model_version)
        
        # Preprocess input
        preprocessed_data = preprocess_input(inputs)
        
        # Convert to tensor
        device = next(model.parameters()).device
        input_tensor = torch.tensor(preprocessed_data, device=device)
        
        # Run inference
        with torch.no_grad():
            predictions = model(input_tensor)
        
        # Postprocess output
        processed_predictions = postprocess_output(predictions)
        
        return jsonify({
            "predictions": processed_predictions,
            "model_version": model_version,
            "prediction_time": time.time() - start_time
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy"})

@app.route("/metadata")
def get_metadata():
    """Get model metadata."""
    return jsonify({
        "model_name": config['model']['name'],
        "versions_available": list(model_cache.keys()),
        "config": config
    })

# Load model on startup
load_model()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000) 