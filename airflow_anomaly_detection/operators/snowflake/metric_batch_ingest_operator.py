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
        """
        
        snowflake_hook = SnowflakeHook(context['params'].get('snowflake_connection_id','snowflake_default'))

        results = snowflake_hook.run(
            sql=self.metric_batch_sql,
        )
        self.log.info(results)
