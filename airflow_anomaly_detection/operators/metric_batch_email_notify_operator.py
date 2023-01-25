import io
from typing import Any

from airflow.models.baseoperator import BaseOperator
from airflow.utils.email import send_email

import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import tempfile
from ascii_graph import Pyasciigraph


class MetricBatchEmailNotifyOperator(BaseOperator):
    """
    Runs logic to package up and email anomalies.

    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        
    def execute(self, context: Any):

        metric_batch_name = context['params']['metric_batch_name']
        gcp_destination_dataset = context['params']['gcp_destination_dataset']
        gcp_ingest_destination_table_name = context['params']['gcp_ingest_destination_table_name']
        gcp_score_destination_table_name = context['params']['gcp_score_destination_table_name']
        alert_emails_to = context['params']['alert_emails_to']
        graph_symbol = context['params'].get('graph_symbol','~')
        anomaly_symbol = context['params'].get('anomaly_symbol','* ')
        normal_symbol = context['params'].get('normal_symbol','  ')
        alert_status_threshold = context['params']['alert_status_threshold']

        data_alert = context['ti'].xcom_pull(key=f'df_alert_{metric_batch_name}')
        df_alert = pd.DataFrame(data_alert)
        df_alert = df_alert.dropna()

        if len(df_alert) > 0:

            df_alert['metric_timestamp'] = pd.to_datetime(df_alert['metric_timestamp']).dt.strftime('%Y-%m-%d %H:%M:%S')

            for metric_name in df_alert['metric_name'].unique():

                df_alert_metric = df_alert[df_alert['metric_name'] == metric_name]
                df_alert_metric = df_alert_metric.sort_values(by='metric_timestamp', ascending=False)
                x = df_alert_metric['metric_value'].round(2).values.tolist()
                labels = (np.where(df_alert_metric['alert_status']==1,anomaly_symbol,normal_symbol) + (df_alert_metric['prob_anomaly_smooth'].round(2)*100).astype('int').astype('str') + '% ' + df_alert_metric['metric_timestamp'].values).to_list()
                data = zip(labels,x)
                graph_title = f"{metric_name} ({df_alert_metric['metric_timestamp'].min()} to {df_alert_metric['metric_timestamp'].max()})"

                graph = Pyasciigraph(
                    titlebar=' ',
                    graphsymbol=graph_symbol,
                    float_format='{0:,.2f}'
                    ).graph(graph_title, data)
                lines = ''
                for i, line in  enumerate(graph):
                    if i <= 1:
                        lines += '\n' + line
                    else:
                        lines += '\n' + f't={0-i+2}'.ljust(6, ' ') + line
                
                qry_sql = f"""
```
select *
from `{ gcp_destination_dataset }.{ gcp_ingest_destination_table_name }` m
join `{ gcp_destination_dataset }.{ gcp_score_destination_table_name }` s
on m.metric_name = s.metric_name and m.metric_timestamp = s.metric_timestamp
where m.metric_name = '{ metric_name }'
order by m.metric_timestamp desc
```
                """

                buf = io.BytesIO()
                fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(20, 10), gridspec_kw={'height_ratios': [2, 1]})
                df_plot = df_alert_metric.set_index('metric_timestamp').sort_index()
                ax1 = df_plot['metric_value'].plot(title=metric_name, ax=axes[0], style='-o')
                x_axis = ax1.axes.get_xaxis()
                x_axis.set_visible(False)
                ax2 = df_plot[['prob_anomaly_smooth','alert_status']].plot(title='anomaly_score', ax=axes[1], rot=45, style=['--','o'], x_compat=True)
                ax2.axhline(alert_status_threshold, color='lightgrey', linestyle='-.')
                ax2.set_xticks(range(len(df_plot)))
                ax2.set_xticklabels([f'{item}' for item in df_plot.index.tolist()], rotation=45)
                fig.savefig(buf, format='jpg', bbox_inches='tight', dpi=250)
                fp = tempfile.NamedTemporaryFile(prefix=f'{metric_name}_')
                fname = f"{fp.name}.jpg"
                with open(fname,'wb') as ff:
                    ff.write(buf.getvalue()) 
                buf.close()

                subject = f"🤷 [{metric_name}] looks anomalous ({df_alert_metric['metric_timestamp'].max()}) 🤷"
                email_message = lines + f'\n\n{qry_sql}'
                email_message = f"<pre>{email_message}</pre>"

                send_email(
                    to=alert_emails_to,
                    subject=subject,
                    html_content=email_message,
                    files=[fname]
                )