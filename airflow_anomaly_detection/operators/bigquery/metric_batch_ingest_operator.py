"""Operator to ingest a batch of metrics into BigQuery."""

from typing import Sequence, Any

from airflow.models.baseoperator import BaseOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook


class BigQueryMetricBatchIngestOperator(BaseOperator):
    """
    Runs some sql to generate some metrics.

    :param metric_batch_sql: sql to be executed when ingesting the metrics
    :type metric_batch_sql: str
    """

    template_fields: Sequence[str] = ["metric_batch_sql"]
    template_fields_renderers = {"metric_batch_sql": "sql"}

    def __init__(self, metric_batch_sql: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.metric_batch_sql = metric_batch_sql
        
    def execute(self, context: Any):
        """
        Executes `insert_job` to generate metrics.
        """
        
        gcp_destination_dataset = context['params'].get('gcp_destination_dataset', 'develop')
        gcp_ingest_destination_table_name = context['params'].get('gcp_ingest_destination_table_name', 'metrics')
        gcp_ingest_write_disposition = context['params'].get('gcp_ingest_write_disposition', 'WRITE_APPEND')
        
        bigquery_hook = BigQueryHook(context['params']['gcp_connection_id'])
        gcp_project_id = bigquery_hook.get_client().project

        bigquery_hook.insert_job(
            configuration={
                "query": {
                    "useLegacySql": False,
                    "query": self.metric_batch_sql,
                    "destinationTable": {
                        "projectId": gcp_project_id,
                        "datasetId": gcp_destination_dataset,
                        "tableId": gcp_ingest_destination_table_name,
                    },
                    "writeDisposition": gcp_ingest_write_disposition,
                    "timePartitioning": {
                        "type": "DAY",
                        "field": "metric_timestamp",
                        "requirePartitionFilter": True,
                    },
                }
            }
        )
