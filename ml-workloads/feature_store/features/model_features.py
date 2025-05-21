from datetime import timedelta
from feast import (
    Entity,
    Feature,
    FeatureView,
    FileSource,
    ValueType,
)

# Define an entity for our model
model = Entity(
    name="model_id",
    value_type=ValueType.STRING,
    description="The identifier of the ML model",
)

# Source for training metrics
training_metrics_source = FileSource(
    path="gs://${GCS_BUCKET_NAME}/features/offline/training_metrics.parquet",
    timestamp_field="timestamp",
    file_format="parquet",
)

# Feature view for training metrics
training_metrics_fv = FeatureView(
    name="training_metrics",
    entities=["model_id"],
    ttl=timedelta(days=365),
    features=[
        Feature(name="accuracy", dtype=ValueType.FLOAT),
        Feature(name="loss", dtype=ValueType.FLOAT),
        Feature(name="training_time", dtype=ValueType.FLOAT),
        Feature(name="num_parameters", dtype=ValueType.INT64),
    ],
    online=True,
    source=training_metrics_source,
    tags={"team": "ml-platform"},
)

# Source for inference metrics
inference_metrics_source = FileSource(
    path="gs://${GCS_BUCKET_NAME}/features/offline/inference_metrics.parquet",
    timestamp_field="timestamp",
    file_format="parquet",
)

# Feature view for inference metrics
inference_metrics_fv = FeatureView(
    name="inference_metrics",
    entities=["model_id"],
    ttl=timedelta(days=365),
    features=[
        Feature(name="latency_p95", dtype=ValueType.FLOAT),
        Feature(name="throughput", dtype=ValueType.FLOAT),
        Feature(name="error_rate", dtype=ValueType.FLOAT),
        Feature(name="memory_usage", dtype=ValueType.FLOAT),
    ],
    online=True,
    source=inference_metrics_source,
    tags={"team": "ml-platform"},
) 