from great_expectations.core import ExpectationConfiguration
from datetime import datetime, timedelta

# Training metrics expectations
training_metrics_expectations = [
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "accuracy",
            "min_value": 0.0,
            "max_value": 1.0,
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "loss",
            "min_value": 0.0,
            "max_value": float('inf'),
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "training_time",
            "min_value": 0.0,
            "max_value": float('inf'),
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "num_parameters",
            "min_value": 0,
            "max_value": float('inf'),
        }
    ),
]

# Inference metrics expectations
inference_metrics_expectations = [
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "latency_p95",
            "min_value": 0.0,
            "max_value": float('inf'),
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "throughput",
            "min_value": 0.0,
            "max_value": float('inf'),
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "error_rate",
            "min_value": 0.0,
            "max_value": 1.0,
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "memory_usage",
            "min_value": 0.0,
            "max_value": float('inf'),
        }
    ),
]

# Common expectations for all feature views
common_expectations = [
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_not_be_null",
        kwargs={
            "column": "model_id",
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_not_be_null",
        kwargs={
            "column": "timestamp",
        }
    ),
    ExpectationConfiguration(
        expectation_type="expect_column_values_to_be_between",
        kwargs={
            "column": "timestamp",
            "min_value": datetime.now() - timedelta(days=365),
            "max_value": datetime.now() + timedelta(minutes=5),
            "parse_strings_as_datetimes": True
        }
    ),
] 