import unittest
from unittest.mock import patch, MagicMock
from pandas import DataFrame
from airflow_anomaly_detection.operators.bigquery.metric_batch_alert_operator import BigQueryMetricBatchAlertOperator

class TestBigQueryMetricBatchAlertOperator(unittest.TestCase):

    @patch('airflow.providers.google.cloud.hooks.bigquery.BigQueryHook.__init__', return_value=None)
    @patch('airflow.providers.google.cloud.hooks.bigquery.BigQueryHook.get_pandas_df')
    def test_execute(self, mock_get_pandas_df, mock_bigquery_hook_init):
        # Mock context
        context: Any = {
            'params': {
                'metric_batch_name': 'test_metric_batch',
                'gcp_connection_id': 'google_cloud_default'
            },
            'ti': MagicMock()  # mock ti object in context to allow xcom_push
        }

        test_df = DataFrame(data={'metric_timestamp': [1, 2, 3, None]}).astype(str)
        mock_get_pandas_df.return_value = test_df

        # Call the execute method
        self.operator = BigQueryMetricBatchAlertOperator(
            task_id='test_task',
            alert_status_sql='SELECT * FROM dataset.table'
            )
        self.operator.execute(context)

        # Validate call to BigQueryHook
        mock_bigquery_hook_init.assert_called_once_with('google_cloud_default')

        # Validate call to get_pandas_df
        mock_get_pandas_df.assert_called_once_with(
            sql=self.operator.alert_status_sql, dialect='standard'
        )

        # Check xcom_push
        context['ti'].xcom_push.assert_called_once_with(
            key=f'df_alert_{context["params"]["metric_batch_name"]}', 
            value=test_df.dropna().to_dict('records')
        )
