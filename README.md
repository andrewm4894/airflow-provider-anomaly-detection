# Anomaly Detection with Apache Airflow

Painless anomaly detection (using [PyOD](https://github.com/yzhao062/pyod)) with Apache Airflow.

1. Create and express your metrics via SQL queries.
1. Some YAML configuration fun.
1. Receive useful alerts when metrics look anomalous.

## Getting Started

Check out the [example dag](https://github.com/andrewm4894/airflow-provider-anomaly-detection/tree/main/airflow_anomaly_detection/example_dags/anomaly-detection-dag/) to get started.

### Installation

Install from [PyPI](https://pypi.org/project/airflow-provider-anomaly-detection/) as usual.

```bash
pip install airflow-provider-anomaly-detection
```

### Configuration

See the example configuration files in the [example dag](https://github.com/andrewm4894/airflow-provider-anomaly-detection/tree/main/airflow_anomaly_detection/example_dags/anomaly-detection-dag/config/) folder. You can use a `defaults.yaml` or specific `<metric-batch>.yaml` for each metric batch if needed.
