from typing import Sequence, Any

from airflow.models.baseoperator import BaseOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

import pickle
import tempfile
from google.cloud import storage
import pandas as pd


class MetricBatchScoreOperator(BaseOperator):
    """
    Runs some sql to generate preprocessed scoring data.

    :param preprocess_sql: sql to be executed when preprocessing the metrics for scoring
    :type preprocess_sql: str
    """

    template_fields: Sequence[str] = ["preprocess_sql"]
    template_fields_renderers = {"preprocess_sql": "sql"}

    def __init__(self, preprocess_sql: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.preprocess_sql = preprocess_sql
        
    def execute(self, context: Any):
        
        gcs_model_bucket = context['params']['gcs_model_bucket']
        gcp_destination_dataset = context['params']['gcp_destination_dataset']
        gcp_score_destination_table_name = context['params']['gcp_score_destination_table_name']

        score_destination_table_full_name = f'{gcp_destination_dataset}.{gcp_score_destination_table_name}'

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

            df_scores = pd.DataFrame()

            for metric_name in metrics_distinct:

                df_X = df_score[df_score['metric_name'] == metric_name]
                X = df_X[[col for col in df_X.columns if col.startswith('x_')]].values

                storage_client = storage.Client(credentials=gcp_credentials)
                bucket = storage_client.get_bucket(gcs_model_bucket)
                model_name = f'{metric_name}.pkl'
                blob = bucket.blob(f'models/{model_name}')
                with tempfile.NamedTemporaryFile() as temp:
                    blob.download_to_filename(temp.name)
                    with open(temp.name, 'rb') as f:
                        model = pickle.load(f)
                
                scores = model.predict_proba(X)
                df_scores_tmp = pd.DataFrame(scores, columns=['prob_normal','prob_anomaly'])
                df_scores_tmp['metric_name'] = metric_name
                df_scores_tmp['metric_timestamp'] = df_X['metric_timestamp'].values
                df_scores = df_scores.append(df_scores_tmp)

            print(f'writing {len(df_scores)} rows into {score_destination_table_full_name}')

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

            bigquery_hook.insert_all(
                dataset_id=gcp_destination_dataset,
                table_id=gcp_score_destination_table_name,
                rows=df_scores.to_dict('records'),
                project_id=gcp_project_id,
            )