"""Operator to ingest a batch of metrics into Snowflake."""

from typing import Sequence, Any

from airflow.models.baseoperator import BaseOperator
from airflow.providers.snowflake.hooks.snowflake import SnowflakeHook


class SnowflakeMetricBatchIngestOperator(BaseOperator):
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
        
        snowflake_destination_dataset = context['params'].get('snowflake_destination_dataset', 'develop')
        snowflake_ingest_destination_table_name = context['params'].get('snowflake_ingest_destination_table_name', 'metrics')
        snowflake_ingest_write_disposition = context['params'].get('snowflake_ingest_write_disposition', 'WRITE_APPEND')
        
        snowflake_hook = SnowflakeHook(context['params']['snowflake_connection_id'])
        snowflake_project_id = snowflake_hook.get_client().project

        snowflake_hook.insert_job(
            configuration={
                "query": {
                    "useLegacySql": False,
                    "query": self.metric_batch_sql,
                    "destinationTable": {
                        "projectId": snowflake_project_id,
                        "datasetId": snowflake_destination_dataset,
                        "tableId": snowflake_ingest_destination_table_name,
                    },
                    "writeDisposition": snowflake_ingest_write_disposition,
                    "timePartitioning": {
                        "type": "DAY",
                        "field": "metric_timestamp",
                        "requirePartitionFilter": True,
                    },
                }
            }
        )
