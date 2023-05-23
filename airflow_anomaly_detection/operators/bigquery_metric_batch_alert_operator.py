"""Operator to flag anomalies in a metric batch."""

from typing import Sequence, Any

from airflow.models.baseoperator import BaseOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook


class BigQueryMetricBatchAlertOperator(BaseOperator):
    """
    Runs some sql to flag anomalies.

    :param alert_status_sql: sql to be executed when flagging anomalies
    :type alert_status_sql: str
    """

    template_fields: Sequence[str] = ["alert_status_sql"]
    template_fields_renderers = {"alert_status_sql": "sql"}

    def __init__(self, alert_status_sql: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.alert_status_sql = alert_status_sql
        
    def execute(self, context: Any):

        metric_batch_name = context['params']['metric_batch_name']

        bigquery_hook = BigQueryHook(context['params']['gcp_connection_id'])

        df_alert = bigquery_hook.get_pandas_df(
            sql=self.alert_status_sql,
            dialect='standard'
        )
        df_alert = df_alert.dropna()
        df_alert['metric_timestamp'] = df_alert['metric_timestamp'].astype(str)

        self.log.info(f'len(df_alert)={len(df_alert)}')

        # push df_alert to xcom to by picked up by downstream notify task
        context['ti'].xcom_push(key=f'df_alert_{metric_batch_name}', value=df_alert.to_dict('records'))
