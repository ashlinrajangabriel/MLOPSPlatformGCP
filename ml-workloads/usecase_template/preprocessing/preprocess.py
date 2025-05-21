import os
import argparse
import yaml
import pandas as pd
import numpy as np
from google.cloud import storage
from typing import Tuple, List
import mlflow
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

def download_data(gcs_path: str, local_path: str) -> str:
    """Download data from GCS to local path."""
    if gcs_path.startswith('gs://'):
        bucket_name = gcs_path.split('/')[2]
        blob_path = '/'.join(gcs_path.split('/')[3:])
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        blob.download_to_filename(local_path)
        return local_path
    return gcs_path

def upload_data(local_path: str, gcs_path: str):
    """Upload data from local path to GCS."""
    if gcs_path.startswith('gs://'):
        bucket_name = gcs_path.split('/')[2]
        blob_path = '/'.join(gcs_path.split('/')[3:])
        
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        
        blob.upload_from_filename(local_path)

def load_data(config: dict) -> pd.DataFrame:
    """Load raw data from source."""
    data_path = config['data']['source_path']
    local_path = '/tmp/raw_data.csv'
    
    # Download if GCS path
    data_path = download_data(data_path, local_path)
    
    # Load data based on file type
    if data_path.endswith('.csv'):
        df = pd.read_csv(data_path)
    elif data_path.endswith('.parquet'):
        df = pd.read_parquet(data_path)
    else:
        raise ValueError(f"Unsupported file format: {data_path}")
    
    return df

def clean_data(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Clean and validate data."""
    # Drop duplicates
    df = df.drop_duplicates()
    
    # Handle missing values
    for col in df.columns:
        if df[col].isnull().sum() > 0:
            if col in config['preprocessing']['fill_values']:
                df[col] = df[col].fillna(config['preprocessing']['fill_values'][col])
            else:
                df = df.dropna(subset=[col])
    
    # Remove outliers if specified
    if config['preprocessing'].get('remove_outliers', False):
        for col in config['preprocessing'].get('outlier_columns', []):
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            df = df[~((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr)))]
    
    return df

def feature_engineering(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    """Create new features and transform existing ones."""
    # Create feature transformers dictionary
    feature_transformers = {}
    
    # Apply numeric scaling
    if config['preprocessing'].get('scale_features', False):
        numeric_features = df.select_dtypes(include=['int64', 'float64']).columns
        scaler = StandardScaler()
        df[numeric_features] = scaler.fit_transform(df[numeric_features])
        feature_transformers['scaler'] = scaler
    
    # Create feature interactions if specified
    if config['preprocessing'].get('feature_interactions', False):
        for feat1, feat2 in config['preprocessing'].get('interaction_pairs', []):
            df[f"{feat1}_{feat2}_interaction"] = df[feat1] * df[feat2]
    
    # Create polynomial features if specified
    if config['preprocessing'].get('polynomial_features', False):
        for feat in config['preprocessing'].get('polynomial_columns', []):
            df[f"{feat}_squared"] = df[feat] ** 2
    
    # Encode categorical variables
    for col in config['preprocessing'].get('categorical_columns', []):
        if col in df.columns:
            df[col] = pd.Categorical(df[col]).codes
    
    return df, feature_transformers

def split_data(df: pd.DataFrame, config: dict) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split data into train, validation, and test sets."""
    # Separate features and target
    X = df.drop(columns=[config['data']['target_column']])
    y = df[config['data']['target_column']]
    
    # First split: train + validation, test
    X_train_val, X_test, y_train_val, y_test = train_test_split(
        X, y,
        test_size=config['preprocessing']['test_size'],
        random_state=config['preprocessing']['random_state']
    )
    
    # Second split: train, validation
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_val, y_train_val,
        test_size=config['preprocessing']['validation_size'],
        random_state=config['preprocessing']['random_state']
    )
    
    # Combine features and target
    train_df = pd.concat([X_train, y_train], axis=1)
    val_df = pd.concat([X_val, y_val], axis=1)
    test_df = pd.concat([X_test, y_test], axis=1)
    
    return train_df, val_df, test_df

def save_data(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame, 
              feature_transformers: dict, config: dict):
    """Save processed data and feature transformers."""
    # Save locally first
    os.makedirs('/tmp/processed', exist_ok=True)
    
    train_path = '/tmp/processed/train.parquet'
    val_path = '/tmp/processed/val.parquet'
    test_path = '/tmp/processed/test.parquet'
    
    train_df.to_parquet(train_path)
    val_df.to_parquet(val_path)
    test_df.to_parquet(test_path)
    
    # Upload to GCS
    upload_data(train_path, config['data']['train_path'])
    upload_data(val_path, config['data']['val_path'])
    upload_data(test_path, config['data']['test_path'])
    
    # Log feature transformers with MLflow
    mlflow.set_tracking_uri(config['mlflow']['tracking_uri'])
    mlflow.set_experiment(config['mlflow']['experiment_name'])
    
    with mlflow.start_run(run_name=f"preprocessing_{config['mlflow']['run_name']}"):
        # Log feature transformers
        for name, transformer in feature_transformers.items():
            mlflow.sklearn.log_model(transformer, f"transformers/{name}")
        
        # Log preprocessing parameters
        mlflow.log_params({
            "n_train_samples": len(train_df),
            "n_val_samples": len(val_df),
            "n_test_samples": len(test_df),
            "features": list(train_df.columns),
            **config['preprocessing']
        })
        
        # Log data statistics
        mlflow.log_metrics({
            "train_mean_target": train_df[config['data']['target_column']].mean(),
            "train_std_target": train_df[config['data']['target_column']].std(),
            "val_mean_target": val_df[config['data']['target_column']].mean(),
            "val_std_target": val_df[config['data']['target_column']].std()
        })

def main(config_path: str):
    """Main preprocessing pipeline."""
    # Load configuration
    with open(config_path) as f:
        config = yaml.safe_load(f)
    
    # Load data
    print("Loading data...")
    df = load_data(config)
    
    # Clean data
    print("Cleaning data...")
    df = clean_data(df, config)
    
    # Feature engineering
    print("Performing feature engineering...")
    df, feature_transformers = feature_engineering(df, config)
    
    # Split data
    print("Splitting data...")
    train_df, val_df, test_df = split_data(df, config)
    
    # Save processed data and transformers
    print("Saving processed data...")
    save_data(train_df, val_df, test_df, feature_transformers, config)
    
    print("Preprocessing completed successfully!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    args = parser.parse_args()
    main(args.config) 