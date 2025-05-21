from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.transfers.local_to_gcs import LocalToGCSOperator
from airflow.providers.google.cloud.operators.gcs import GCSDeleteObjectsOperator
from feast import FeatureStore
import pandas as pd
import os
from great_expectations.core import ExpectationSuite
from great_expectations.dataset import PandasDataset
from feature_store.validation.expectations import (
    training_metrics_expectations,
    inference_metrics_expectations,
    common_expectations
)
import mlflow

# Feature store initialization
def get_feature_store():
    return FeatureStore(repo_path="/opt/ml/feature_store")

# Feature computation functions
def compute_batch_features(**context):
    """Compute features and save as parquet files locally"""
    # Example computation of training metrics
    training_metrics_df = pd.DataFrame({
        'model_id': ['model1', 'model2'],
        'timestamp': [datetime.now(), datetime.now()],
        'accuracy': [0.95, 0.92],
        'loss': [0.05, 0.08],
        'training_time': [120.5, 150.2],
        'num_parameters': [1000000, 2000000]
    })
    
    # Example computation of inference metrics
    inference_metrics_df = pd.DataFrame({
        'model_id': ['model1', 'model2'],
        'timestamp': [datetime.now(), datetime.now()],
        'latency_p95': [0.15, 0.18],
        'throughput': [100.5, 95.2],
        'error_rate': [0.02, 0.03],
        'memory_usage': [1.5, 2.1]
    })
    
    # Save locally as parquet
    local_path = "/tmp/feature_store"
    os.makedirs(local_path, exist_ok=True)
    
    training_metrics_df.to_parquet(f"{local_path}/training_metrics.parquet", index=False)
    inference_metrics_df.to_parquet(f"{local_path}/inference_metrics.parquet", index=False)
    
    return {
        'training_metrics_path': f"{local_path}/training_metrics.parquet",
        'inference_metrics_path': f"{local_path}/inference_metrics.parquet"
    }

def materialize_features(**context):
    """Materialize features from offline store to online store"""
    store = get_feature_store()
    store.materialize_incremental(
        end_date=context['execution_date'],
        feature_views=None  # Materialize all feature views
    )

def validate_features(**context):
    """Validate feature quality and freshness using Great Expectations"""
    ti = context['task_instance']
    training_metrics_df = ti.xcom_pull(task_ids='compute_batch_features')['training_metrics_df']
    inference_metrics_df = ti.xcom_pull(task_ids='compute_batch_features')['inference_metrics_df']
    
    # Create validation suites
    training_suite = ExpectationSuite(expectation_suite_name="training_metrics_suite")
    inference_suite = ExpectationSuite(expectation_suite_name="inference_metrics_suite")
    
    # Add expectations to suites
    for exp in common_expectations + training_metrics_expectations:
        training_suite.add_expectation(exp)
    for exp in common_expectations + inference_metrics_expectations:
        inference_suite.add_expectation(exp)
    
    # Validate datasets
    training_dataset = PandasDataset(training_metrics_df, expectation_suite=training_suite)
    inference_dataset = PandasDataset(inference_metrics_df, expectation_suite=inference_suite)
    
    training_results = training_dataset.validate()
    inference_results = inference_dataset.validate()
    
    # Check if validation passed
    if not (training_results.success and inference_results.success):
        raise ValueError("Feature validation failed. Check the validation results in MLflow.")
    
    # Log validation results to MLflow
    with mlflow.start_run(run_name="feature_validation"):
        mlflow.log_dict(training_results.to_json_dict(), "training_validation.json")
        mlflow.log_dict(inference_results.to_json_dict(), "inference_validation.json")

default_args = {
    'owner': 'ml_platform',
    'depends_on_past': False,
    'email': ['ml-alerts@company.com'],
    'email_on_failure': True,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'feature_store_pipeline',
    default_args=default_args,
    description='Feature store pipeline for ML workloads',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=['ml', 'feature-store'],
) as dag:

    # Compute features and save locally
    compute_features = PythonOperator(
        task_id='compute_batch_features',
        python_callable=compute_batch_features,
    )

    # Upload training metrics to GCS
    upload_training_metrics = LocalToGCSOperator(
        task_id='upload_training_metrics',
        src='{{ task_instance.xcom_pull(task_ids="compute_batch_features")["training_metrics_path"] }}',
        dst='features/offline/training_metrics.parquet',
        bucket='${GCS_BUCKET_NAME}',
        gcp_conn_id='google_cloud_default',
    )

    # Upload inference metrics to GCS
    upload_inference_metrics = LocalToGCSOperator(
        task_id='upload_inference_metrics',
        src='{{ task_instance.xcom_pull(task_ids="compute_batch_features")["inference_metrics_path"] }}',
        dst='features/offline/inference_metrics.parquet',
        bucket='${GCS_BUCKET_NAME}',
        gcp_conn_id='google_cloud_default',
    )

    # Materialize features to online store
    materialize = PythonOperator(
        task_id='materialize_features',
        python_callable=materialize_features,
    )

    # Validate features
    validate = PythonOperator(
        task_id='validate_features',
        python_callable=validate_features,
    )

    # Clean up temporary files
    cleanup_gcs = GCSDeleteObjectsOperator(
        task_id='cleanup_old_files',
        bucket_name='${GCS_BUCKET_NAME}',
        prefix='features/offline/archive/',
        gcp_conn_id='google_cloud_default',
    )

    # Define task dependencies
    compute_features >> [upload_training_metrics, upload_inference_metrics] >> materialize >> validate >> cleanup_gcs 