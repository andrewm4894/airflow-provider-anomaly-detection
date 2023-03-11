"""Runs logic to package up and email anomalies."""

import io
import os
from typing import Any

from airflow.models.baseoperator import BaseOperator
from airflow.utils.email import send_email
from airflow.exceptions import AirflowException

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import tempfile
from ascii_graph import Pyasciigraph


class ConditionalFormat:
    def __init__(self, threshold=1):
        self.threshold = threshold

    def format(self, value):
        if isinstance(value, (int, float)):
            if value < self.threshold:
                return '{:,.2f}'.format(value)
            else:
                return '{:,.0f}'.format(value)
        else:
            raise TypeError(f"Unsupported type: {type(value)}")


class MetricBatchEmailNotifyOperator(BaseOperator):
    """
    Runs logic to package up and email anomalies.

    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def make_alert_lines(self, df_alert_metric, graph_symbol, anomaly_symbol, normal_symbol, alert_float_format):
            
            df_alert_metric = df_alert_metric.sort_values(by='metric_timestamp', ascending=False)
            x = df_alert_metric['metric_value'].round(2).values.tolist()
            labels = (np.where(df_alert_metric['alert_status']==1,anomaly_symbol,normal_symbol) + (df_alert_metric['prob_anomaly_smooth'].round(2)*100).astype('int').astype('str') + '% ' + df_alert_metric['metric_timestamp'].values).to_list()
            data = zip(labels,x)
            graph_title = f"{df_alert_metric['metric_name'].unique()[0]} ({df_alert_metric['metric_timestamp'].min()} to {df_alert_metric['metric_timestamp'].max()})"
    
            graph = Pyasciigraph(
                titlebar=' ',
                graphsymbol=graph_symbol,
                float_format=alert_float_format
                ).graph(graph_title, data)
            lines = ''
            for i, line in  enumerate(graph):
                if i <= 1:
                    lines += '\n' + line
                else:
                    lines += '\n' + f't={0-i+2}'.ljust(6, ' ') + line
            
            return lines

    def make_qry_sql(self, metric_name, gcp_destination_dataset, gcp_ingest_destination_table_name, gcp_score_destination_table_name):
        
        qry_sql = f"""
        ```sql
        select *
        from `{ gcp_destination_dataset }.{ gcp_ingest_destination_table_name }` m
        join `{ gcp_destination_dataset }.{ gcp_score_destination_table_name }` s
        on m.metric_name = s.metric_name and m.metric_timestamp = s.metric_timestamp
        where date(m.metric_timestamp) >= date_sub(current_date(), interval 7 day) and m.metric_name = '{ metric_name }'
        order by m.metric_timestamp desc limit 100
        ```
        """.replace('        ','')

        return qry_sql

    def make_temp_chart_file(self, df_alert_metric, metric_name, alert_status_threshold):

        buf = io.BytesIO()
        fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(20, 10), gridspec_kw={'height_ratios': [2, 1]})
        df_plot = df_alert_metric.set_index('metric_timestamp').sort_index()
        ax1 = df_plot['metric_value'].plot(title=metric_name, ax=axes[0], style='-o')
        x_axis = ax1.axes.get_xaxis()
        x_axis.set_visible(False)
        ax2 = df_plot[['prob_anomaly_smooth','alert_status']].plot(title='anomaly_score smooth', ax=axes[1], rot=45, style=['--','o'], x_compat=True)
        ax2.axhline(alert_status_threshold, color='lightgrey', linestyle='-.')
        ax2.set_xticks(range(len(df_plot)))
        ax2.set_xticklabels([f'{item}' for item in df_plot.index.tolist()], rotation=45)
        fig.savefig(buf, format='jpg', bbox_inches='tight', dpi=250)
        fp = tempfile.NamedTemporaryFile(prefix=f'{metric_name}_', delete=False)
        fname = f"{fp.name}.jpg"
        with open(fname,'wb') as ff:
            ff.write(buf.getvalue()) 
        buf.close()

        return fp, fname
        
    def execute(self, context: Any):

        metric_batch_name = context['params']['metric_batch_name']
        gcp_destination_dataset = context['params'].get('gcp_destination_dataset','develop')
        gcp_ingest_destination_table_name = context['params'].get('gcp_ingest_destination_table_name','metrics')
        gcp_score_destination_table_name = context['params'].get('gcp_score_destination_table_name','metrics_scored')
        alert_emails_to = os.getenv('AIRFLOW_ALERT_EMAILS', context['params']['alert_emails_to']).split(',')
        alert_subject_emoji = context['params'].get('alert_subject_emoji','🔥')
        graph_symbol = context['params'].get('graph_symbol','~')
        anomaly_symbol = context['params'].get('anomaly_symbol','* ')
        normal_symbol = context['params'].get('normal_symbol','  ')
        alert_float_format = context['params'].get('alert_float_format',ConditionalFormat())
        alert_status_threshold = context['params'].get('alert_status_threshold',0.9)
        alert_airflow_fail_on_alert = context['params'].get('alert_airflow_fail_on_alert',False)

        # get df_alert from xcom
        data_alert = context['ti'].xcom_pull(key=f'df_alert_{metric_batch_name}')
        df_alert = pd.DataFrame(data_alert)
        df_alert = df_alert.dropna()

        if len(df_alert) > 0:

            df_alert['metric_timestamp'] = pd.to_datetime(df_alert['metric_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

            for metric_name in df_alert['metric_name'].unique():

                df_alert_metric = df_alert[df_alert['metric_name'] == metric_name]
                metric_timestamp_max = df_alert_metric['metric_timestamp'].max()

                alert_lines = self.make_alert_lines(
                    df_alert_metric=df_alert_metric,
                    graph_symbol=graph_symbol,
                    anomaly_symbol=anomaly_symbol,
                    normal_symbol=normal_symbol,
                    alert_float_format=alert_float_format
                )

                qry_sql = self.make_qry_sql(
                    metric_name=metric_name,
                    gcp_destination_dataset=gcp_destination_dataset,
                    gcp_ingest_destination_table_name=gcp_ingest_destination_table_name,
                    gcp_score_destination_table_name=gcp_score_destination_table_name
                )

                subject = f"{alert_subject_emoji} [{metric_name}] looks anomalous ({metric_timestamp_max}) {alert_subject_emoji}"
                email_message = alert_lines + f'\n\n{qry_sql.lstrip()}'
                email_message = f"<pre>{email_message}</pre>"

                self.log.info(subject)
                self.log.info(email_message)

                fp, fname = self.make_temp_chart_file(df_alert_metric, metric_name, alert_status_threshold)

                send_email(
                    to=alert_emails_to,
                    subject=subject,
                    html_content=email_message,
                    files=[fname]
                )

                # remove temp file
                fp.close()
                os.remove(fname)

                self.log.info(f'alert sent, subject={subject}, to={alert_emails_to}')

                if alert_airflow_fail_on_alert:
                    raise AirflowException(f'{subject}{email_message}')  

        else:

            self.log.info(f'no alert, metric_batch_name={metric_batch_name}')
