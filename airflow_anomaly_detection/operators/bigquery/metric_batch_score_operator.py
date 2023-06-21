"""Runs some sql to generate preprocessed scoring data and uses a model per metric_name to score the data."""

from typing import Sequence, Any
import os

from airflow.models.baseoperator import BaseOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.exceptions import AirflowException

import pickle
import tempfile
from google.cloud import storage
import pandas as pd


class BigQueryMetricBatchScoreOperator(BaseOperator):
    """
    Runs some sql to generate preprocessed scoring data and uses a model per metric_name to score the data.

    :param preprocess_sql: sql to be executed when preprocessing the metrics for scoring
    :type preprocess_sql: str
    """

    template_fields: Sequence[str] = ["preprocess_sql"]
    template_fields_renderers = {"preprocess_sql": "sql"}

    def __init__(self, preprocess_sql: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.preprocess_sql = preprocess_sql
        
    def execute(self, context: Any):
        
        gcs_model_bucket = os.getenv('AIRFLOW_AD_GCS_MODEL_BUCKET', context['params']['gcs_model_bucket'])
        gcp_destination_dataset = context['params'].get('gcp_destination_dataset', 'develop')
        gcp_score_destination_table_name = context['params'].get('gcp_score_destination_table_name', 'metrics_scored')

        bigquery_hook = BigQueryHook(context['params']['gcp_connection_id'])
        bigquery_client = bigquery_hook.get_client()
        gcp_project_id = bigquery_client.project
        gcp_credentials = bigquery_client._credentials

        df_score = bigquery_hook.get_pandas_df(
            sql=self.preprocess_sql,
            dialect='standard'
        )

        if len(df_score) > 0:
        
            metrics_distinct = df_score['metric_name'].unique()

            # create empty dataframe to store scores
            df_scores = pd.DataFrame()

            # process each metric_name
            for metric_name in metrics_distinct:

                # filter for metric_name
                df_X = df_score[df_score['metric_name'] == metric_name].reset_index()

                # drop columns that are not needed for scoring
                X = df_X[[col for col in df_X.columns if col.startswith('x_')]].values

                try:
                    # load model from GCS
                    storage_client = storage.Client(credentials=gcp_credentials)
                    bucket = storage_client.get_bucket(gcs_model_bucket)
                    model_name = f'{metric_name}.pkl'
                    blob = bucket.blob(f'models/{model_name}')
                    with tempfile.NamedTemporaryFile() as temp:
                        blob.download_to_filename(temp.name)
                        with open(temp.name, 'rb') as f:
                            model = pickle.load(f)
                except Exception as e:
                    self.log(f"An error occurred: {e}")
                    if context['params'].get('airflow_fail_on_model_load_error', True):
                        raise AirflowException(f"An error occurred: {e}")
                    else:
                        self.log.info(f"Skipping metric_name {metric_name}")
                        continue
                
                # score
                scores = model.predict_proba(X)
                
                # create dataframe with scores
                df_scores_tmp = pd.DataFrame(scores, columns=['prob_normal','prob_anomaly'])
                df_scores_tmp['metric_name'] = metric_name
                df_scores_tmp['metric_timestamp'] = df_X['metric_timestamp'].values

                if context['params'].get('airflow_log_scores', False):
                    self.log.info(
                        pd.concat([df_X, df_scores_tmp[['prob_normal','prob_anomaly']]],axis=1).transpose().to_string()
                    )

                # append to df_scores
                df_scores = pd.concat([df_scores, df_scores_tmp])

            # check if table exists and if not create it and partition by metric_timestamp
            if not bigquery_hook.table_exists(
                table_id=gcp_score_destination_table_name,
                dataset_id=gcp_destination_dataset,
                project_id=gcp_project_id,
            ):
                bigquery_hook.create_empty_table(
                    table_id=gcp_score_destination_table_name,
                    dataset_id=gcp_destination_dataset,
                    project_id=gcp_project_id,
                    time_partitioning={
                        'type': 'DAY', 
                        'field': 'metric_timestamp', 
                        'requirePartitionFilter': True
                    },
                    schema_fields=[
                        {'name': 'metric_timestamp', 'type': 'TIMESTAMP', 'mode': 'REQUIRED'},
                        {'name': 'metric_name', 'type': 'STRING', 'mode': 'REQUIRED'},
                        {'name': 'prob_normal', 'type': 'FLOAT', 'mode': 'REQUIRED'},
                        {'name': 'prob_anomaly', 'type': 'FLOAT', 'mode': 'REQUIRED'},
                    ],
                )

            # insert scores into bigquery
            bigquery_hook.insert_all(
                dataset_id=gcp_destination_dataset,
                table_id=gcp_score_destination_table_name,
                rows=df_scores.to_dict('records'),
                project_id=gcp_project_id,
            )

            self.log.info(f'{len(df_scores)} rows written into {gcp_project_id}.{gcp_destination_dataset}.{gcp_score_destination_table_name}')

        else:
            self.log.info('No data to score')
