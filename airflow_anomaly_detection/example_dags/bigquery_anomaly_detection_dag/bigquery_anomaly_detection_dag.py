"""
Example DAG for Airflow Anomaly Detection

This DAG is an example of how to use the Airflow Anomaly Detection package.

The code below creates four separate dags that run independently:
    - ingest: ingest metrics based on sql defined in the relevant metric batch file under /sql/metrics/<metric-batch>.sql.
    - train: train a model based on the metrics ingested.
    - score: score the metrics ingested using latest trained model.
    - alert: alert based on recent scores and send an email if anomalies are found.

"""

import os
import pendulum
import yaml
from airflow.decorators import dag
from airflow_anomaly_detection.operators.bigquery.metric_batch_ingest_operator import BigQueryMetricBatchIngestOperator
from airflow_anomaly_detection.operators.bigquery.metric_batch_train_operator import BigQueryMetricBatchTrainOperator
from airflow_anomaly_detection.operators.bigquery.metric_batch_score_operator import BigQueryMetricBatchScoreOperator
from airflow_anomaly_detection.operators.bigquery.metric_batch_alert_operator import BigQueryMetricBatchAlertOperator
from airflow_anomaly_detection.operators.metric_batch_email_notify_operator import MetricBatchEmailNotifyOperator
from airflow_anomaly_detection.utils import get_metric_batch_configs


##########################################
# PARAMS
##########################################

# params
default_args = {
    'email_on_failure': True,
    'email': os.getenv('AIRFLOW_ALERT_EMAILS', 'youremail@example.com').split(',')
}
dag_folder_name = 'bigquery_anomaly_detection_dag'
dags_folder = os.getenv('AIRFLOW__CORE__DAGS_FOLDER', '/opt/airflow/dags')
#dags_folder = '/home/airflow/gcs/dags/' # dags folder for composer
source_dir = f"{dags_folder}/{dag_folder_name}"
config_dir = f'{source_dir}/config'
sql_dir = f'{source_dir}/sql'

# get configs
metric_batch_configs = get_metric_batch_configs(config_dir)

# read defaults
with open(f'{config_dir}/defaults.yaml') as yaml_file:
    metric_batch_config_defaults = yaml.safe_load(yaml_file)

##########################################
# GENERATE DAGS
##########################################

# process each "metric_batch" config
for metric_batch_config_file in metric_batch_configs:

    with open(metric_batch_config_file) as yaml_file:
        metric_batch_config_tmp = yaml.safe_load(yaml_file)

    # merge defaults
    metric_batch_config = metric_batch_config_defaults.copy()
    metric_batch_config.update(metric_batch_config_tmp)

    # get params
    metric_batch_name = metric_batch_config.get('metric_batch_name')
    metric_batch_description = metric_batch_config.get('metric_batch_description')
    
    # read sql based metric definitions
    with open(f'{sql_dir}/metrics/{metric_batch_name}.sql', 'r') as file:
        metric_batch_sql = file.read()
    
    # read sql based preprocess code and logic
    with open(f'{sql_dir}/preprocess.sql', 'r') as file:
        preprocess_sql = file.read()

    # read sql based alert code and logic
    with open(f'{sql_dir}/alert_status.sql', 'r') as file:
        alert_status_sql = file.read()
    
    ##########################################
    # INGESTION DAG
    ##########################################

    # create ingestion dag
    @dag(
        dag_id=f"{metric_batch_config.get('dag_name_prefix', '')}{metric_batch_name}_ingestion{metric_batch_config.get('dag_name_suffix', '')}",
        description=f'ingestion dag for {metric_batch_name}',
        start_date=pendulum.from_format(metric_batch_config['airflow_start_date'], 'YYYY-MM-DD'),
        schedule_interval=metric_batch_config.get('airflow_ingest_schedule_interval', '@once'),
        catchup=metric_batch_config.get('airflow_catchup', False),
        params=metric_batch_config,
        default_args=default_args,
    )
    def metric_ingestion_dag():

        metric_batch_ingest = BigQueryMetricBatchIngestOperator(
            task_id=f'metric_batch_ingest_{metric_batch_name}',
            metric_batch_sql=metric_batch_sql
        )


    metric_ingestion_dag()

    ##########################################
    # TRAINING DAG
    ##########################################

    # create training dag
    @dag(
        dag_id=f"{metric_batch_config.get('dag_name_prefix', '')}{metric_batch_name}_training{metric_batch_config.get('dag_name_suffix', '')}",
        description=f'training dag for {metric_batch_name}',
        start_date=pendulum.from_format(metric_batch_config['airflow_start_date'], 'YYYY-MM-DD'),
        schedule_interval=metric_batch_config.get('airflow_training_schedule_interval', '@once'),
        catchup=metric_batch_config.get('airflow_catchup', False),
        params=metric_batch_config,
        default_args=default_args,
    )
    def metric_training_dag():

        metric_batch_train = BigQueryMetricBatchTrainOperator(
            task_id=f'metric_batch_train_{metric_batch_name}',
            preprocess_sql=preprocess_sql,
            params={
                **metric_batch_config,
                **{
                    'max_n': metric_batch_config.get('train_max_n', 1000),
                    'max_n_days_ago': metric_batch_config.get('train_max_n_days_ago', 7),
                    'metric_last_updated_hours_ago_max': metric_batch_config.get('train_metric_last_updated_hours_ago_max', 24),
                },
            }
        )


    metric_training_dag()

    ##########################################
    # SCORING DAG
    ##########################################

    # create scoring dag
    @dag(
        dag_id=f"{metric_batch_config.get('dag_name_prefix', '')}{metric_batch_name}_scoring{metric_batch_config.get('dag_name_suffix', '')}",
        description=f'scoring dag for {metric_batch_name}',
        start_date=pendulum.from_format(metric_batch_config['airflow_start_date'], 'YYYY-MM-DD'),
        schedule_interval=metric_batch_config.get('airflow_scoring_schedule_interval', '@once'),
        catchup=metric_batch_config.get('airflow_catchup', False),
        params=metric_batch_config,
        default_args=default_args,
    )
    def metric_scoring_dag():

        metric_batch_score = BigQueryMetricBatchScoreOperator(
            task_id=f'metric_batch_score_{metric_batch_name}',
            preprocess_sql=preprocess_sql,
            params={
                **metric_batch_config,
                **{
                    'max_n': metric_batch_config.get('score_max_n', 1),
                    'max_n_days_ago': metric_batch_config.get('score_max_n_days_ago', 2),
                    'metric_last_updated_hours_ago_max': metric_batch_config.get('score_metric_last_updated_hours_ago_max', 24),
                },
            },
        )
    
    metric_scoring_dag()

    ##########################################
    # ALERTING DAG
    ##########################################

    # create alerting dag
    @dag(
        dag_id=f"{metric_batch_config.get('dag_name_prefix', '')}{metric_batch_name}_alerting{metric_batch_config.get('dag_name_suffix', '')}",
        description=f'alerting dag for {metric_batch_name}',
        start_date=pendulum.from_format(metric_batch_config['airflow_start_date'], 'YYYY-MM-DD'),
        schedule_interval=metric_batch_config.get('airflow_alerting_schedule_interval', '@once'),
        catchup=metric_batch_config.get('airflow_catchup', False),
        params=metric_batch_config,
        default_args=default_args,
    )
    def metric_alerting_dag():

        metric_batch_alert = BigQueryMetricBatchAlertOperator(
            task_id=f'metric_batch_alert_{metric_batch_name}',
            alert_status_sql=alert_status_sql,
            params={
                **metric_batch_config,
                **{'max_n_days_ago': metric_batch_config.get('alert_max_n_days_ago', 3)},
            },
        )

        metric_batch_email_notify = MetricBatchEmailNotifyOperator(
            task_id=f'metric_batch_email_notify_{metric_batch_name}',
            params=metric_batch_config
        )

        metric_batch_alert >> metric_batch_email_notify
    
    metric_alerting_dag()

