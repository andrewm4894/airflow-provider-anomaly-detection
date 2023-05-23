# Airflow Anomaly Detection - Example Dag

In this folder is an example dag using this provider and some example sql and config files.

## Dag Structure

- `bigquery_anomaly_detection_dag.py` - The dag file.
- `config/` - Directory containing the config files.
- `config/defaults.yaml` - The default config file.
- `config/metrics_hourly.yaml` - The config file for the hourly metrics batch.
- `sql/` - Directory containing the sql files.
- `sql/preprocess.sql` - The template sql file to preprocess metrics for training and scoring.
- `sql/alert_status.sql` - The template sql file to get the alert status for a metric.
- `sql/metrics/` - Directory containing the sql files for the metrics.
- `sql/metrics/metrics_hourly.sql` - The sql file for the hourly metrics batch. In this example they are just random numbers to show the expected structure and format.
