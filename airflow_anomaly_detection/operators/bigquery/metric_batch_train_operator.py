"""Runs some sql to generate preprocessed training data and trains a model per metric_name."""

from typing import Sequence, Any
import os
import time

from airflow.models.baseoperator import BaseOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook

import pickle
from pyod.models.iforest import IForest
import tempfile
from google.cloud import storage


class BigQueryMetricBatchTrainOperator(BaseOperator):
    """
    Runs some sql to generate preprocessed training data and trains a model per metric_name.

    :param preprocess_sql: sql to be executed when preprocessing the metrics for training
    :type preprocess_sql: str
    """

    template_fields: Sequence[str] = ["preprocess_sql"]
    template_fields_renderers = {"preprocess_sql": "sql"}

    def __init__(self, preprocess_sql: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.preprocess_sql = preprocess_sql
        
    def execute(self, context: Any):
        
        gcp_credentials = BigQueryHook(context['params']['gcp_connection_id']).get_client()._credentials
        gcs_model_bucket = os.getenv('AIRFLOW_AD_GCS_MODEL_BUCKET', context['params']['gcs_model_bucket'])
        model_type = context['params'].get('model_type','iforest')
        model_params = context['params'].get('model_params',{'contamination' : 0.1})

        bigquery_hook = BigQueryHook(context['params']['gcp_connection_id'])

        df_train = bigquery_hook.get_pandas_df(
            sql=self.preprocess_sql,
            dialect='standard'
        )

        if len(df_train) > 0:
        
            metrics_distinct = df_train['metric_name'].unique()

            for metric_name in metrics_distinct:

                X = df_train[df_train['metric_name'] == metric_name]
                X = X[[col for col in X.columns if col.startswith('x_')]]
                
                # shuffle X
                X = X.sample(frac=1).reset_index(drop=True)

                if model_type == 'iforest':
                    model = IForest(**model_params)
                else:
                    raise ValueError(f'model_type {model_type} is not supported')
                
                time_start_train = time.time()
                model.fit(X)
                time_end_train = time.time()
                train_time = time_end_train - time_start_train

                with tempfile.NamedTemporaryFile() as temp:
                    pickle.dump(model, temp)
                    temp.flush()
                    storage_client = storage.Client(credentials=gcp_credentials)
                    bucket = storage_client.get_bucket(gcs_model_bucket)
                    model_name = f'{metric_name}.pkl'
                    blob = bucket.blob(f'models/{model_name}')
                    blob.upload_from_filename(temp.name)
                    self.log.info(f'trained model {model_name} (n={len(X)}, train_time={round(train_time,2)} secs) has been uploaded to gs://{gcs_model_bucket}/models/{model_name}')

        else:
            self.log.info('no training data available')
