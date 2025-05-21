import os
import mlflow
import random
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

# MLflow tracking URI will be automatically set by the environment
# But you can override it if needed:
# mlflow.set_tracking_uri("https://mlflow.your-domain.com")

def run_test_experiment():
    # Create sample dataset
    X, y = make_classification(n_samples=1000, n_features=10, random_state=42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)

    # Start MLflow run
    with mlflow.start_run(experiment_name="test-experiment"):
        # Set parameters
        n_estimators = random.randint(10, 100)
        max_depth = random.randint(3, 10)
        
        print(f"Training model with n_estimators={n_estimators}, max_depth={max_depth}")
        
        # Log parameters
        mlflow.log_param("n_estimators", n_estimators)
        mlflow.log_param("max_depth", max_depth)
        
        # Train model
        rf = RandomForestClassifier(n_estimators=n_estimators, 
                                  max_depth=max_depth,
                                  random_state=42)
        rf.fit(X_train, y_train)
        
        # Make predictions and calculate accuracy
        y_pred = rf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        print(f"Model accuracy: {accuracy:.4f}")
        
        # Log metrics
        mlflow.log_metric("accuracy", accuracy)
        
        # Log model
        mlflow.sklearn.log_model(rf, "random-forest-model")
        
        print("Experiment completed and logged to MLflow")
        print(f"Run ID: {mlflow.active_run().info.run_id}")

if __name__ == "__main__":
    run_test_experiment() 