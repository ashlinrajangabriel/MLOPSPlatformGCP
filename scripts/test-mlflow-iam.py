#!/usr/bin/env python3
import os
import mlflow
import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

def get_gcp_token():
    """Get GCP OAuth token for Cloud SQL IAM authentication."""
    try:
        # Try getting credentials from compute engine metadata
        credentials, project = google.auth.default()
    except Exception:
        # Fall back to service account file if running locally
        credentials = service_account.Credentials.from_service_account_file(
            'mlflow-sa-key.json',
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
    
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)
    return credentials.token

def test_mlflow_connection():
    """Test MLflow connection and basic operations."""
    print("Testing MLflow connection...")
    
    # Get current tracking URI
    tracking_uri = mlflow.get_tracking_uri()
    print(f"MLflow Tracking URI: {tracking_uri}")
    
    # List experiments
    experiments = mlflow.search_experiments()
    print("\nAvailable Experiments:")
    for exp in experiments:
        print(f"- {exp.name} (ID: {exp.experiment_id})")

def run_test_experiment():
    """Run a test ML experiment with MLflow tracking."""
    print("\nStarting test experiment...")
    
    # Create sample dataset
    X, y = make_classification(n_samples=1000, n_features=10, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
    
    # Start MLflow run
    with mlflow.start_run(experiment_name="iam-test") as run:
        print(f"Run ID: {run.info.run_id}")
        
        # Train model
        rf = RandomForestClassifier(n_estimators=100, random_state=42)
        rf.fit(X_train, y_train)
        
        # Log parameters
        mlflow.log_param("n_estimators", 100)
        mlflow.log_param("test_size", 0.2)
        
        # Make predictions and calculate metrics
        y_pred = rf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        # Log metrics
        mlflow.log_metric("accuracy", accuracy)
        print(f"Model accuracy: {accuracy:.4f}")
        
        # Log model
        mlflow.sklearn.log_model(rf, "random-forest-model")
        print("Model logged successfully")
        
        # Test artifact storage
        with open("test.txt", "w") as f:
            f.write("Test artifact content")
        mlflow.log_artifact("test.txt")
        print("Artifact logged successfully")

def main():
    """Main test function."""
    try:
        # Test connection
        test_mlflow_connection()
        
        # Run test experiment
        run_test_experiment()
        
        print("\nAll tests completed successfully!")
        
    except Exception as e:
        print(f"\nError during testing: {str(e)}")
        raise

if __name__ == "__main__":
    main() 