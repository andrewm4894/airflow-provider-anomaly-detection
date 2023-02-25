"""Runs logic to package up and email anomalies."""
from __future__ import unicode_literals
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
#from airflow_anomaly_detection.asciigraph import Pyasciigraph
import sys
import re
import copy

if sys.version < '3' or sys.version.startswith('3.0.') or sys.version.startswith('3.1.') or sys.version.startswith('3.2.'):
    from collections import Iterable
else:
    from collections.abc import Iterable


class ConditionalFormat:
    def __init__(self, threshold=1):
        self.threshold = threshold

    def format(self, value):
        if isinstance(value, (int, float)):
            if value < self.threshold:
                return '${:,.2f}'.format(value)
            else:
                return '${:,.0f}'.format(value)
        else:
            raise TypeError(f"Unsupported type: {type(value)}")


class PyasciigraphCustom:

    def __init__(self, line_length=79,
                 min_graph_length=50,
                 separator_length=2,
                 force_max_value=None,
                 graphsymbol=None,
                 multivalue=True,
                 human_readable=None,
                 float_format='conditional',
                 titlebar='#'
                 ):
        """Constructor of Pyasciigraph

        :param line_length: the max number of char on a line
          if any line cannot be shorter,
          it will go over this limit.
          Default: 79
        :type line_length: int
        :param min_graph_length: the min number of char
          used by the graph itself.
          Default: 50
        :type min_graph_length: int
        :param force_max_value: if provided, force a max value in order to graph
          each line with respect to it (only taking the actual max value if
          it is greater).
        :type: force_max_value: int
        :param separator_length: the length of field separator.
          Default: 2
        :type separator_length: int
        :param graphsymbol: the symbol used for the graph bar.
          Default: '█'
        :type graphsymbol: str or unicode (length one)
        :param multivalue: displays all the values if multivalued when True.
          displays only the max value if False
          Default: True
        :type multivalue: boolean
        :param human_readable: trigger human readable display (K, G, etc)
          Default: None (raw value display)

          * 'si' for power of 1000

          * 'cs' for power of 1024

          * any other value for raw value display)

        :type human_readable: string (si, cs, none)
        :param float_format: formatting of the float value
          Default: '{0:.0f}' (convert to integers).
          expample: '{:,.2f}' (2 decimals, '.' to separate decimal and int,
          ',' every three power of tens).
        :param titlebar: sets the character(s) for the horizontal title bar
          Default: '#'
        :type titlebar: string
        """

        self.line_length = line_length
        self.separator_length = separator_length
        self.min_graph_length = min_graph_length
        self.max_value = force_max_value
        self.float_format = ConditionalFormat() if float_format=='conditional' else float_format
        self.titlebar = titlebar
        if graphsymbol is None:
            self.graphsymbol = self._u('█')
        else:
            self.graphsymbol = graphsymbol
        if self._len_noansi(self.graphsymbol) != 1:
            raise Exception('Bad graphsymbol length, must be 1',
                            self._len_noansi(self.graphsymbol))
        self.multivalue = multivalue
        self.hsymbols = [self._u(''), self._u('K'), self._u('M'),
                         self._u('G'), self._u('T'), self._u('P'),
                         self._u('E'), self._u('Z'), self._u('Y')]

        if human_readable == 'si':
            self.divider = 1000
        elif human_readable == 'cs':
            self.divider = 1024
        else:
            self.divider = None

    @staticmethod
    def _len_noansi(string):
        l = len(re.sub('\x1b[^m]*m', '', string))
        return l

    def _trans_hr(self, value):

        if self.divider is None:
            return self.float_format.format(value)
        vl = value
        for hs in self.hsymbols:
            new_val = vl / self.divider
            if new_val < 1:
                return self.float_format.format(vl) + hs
            else:
                vl = new_val
        return self.float_format.format(vl * self.divider) + hs

    @staticmethod
    def _u(x):
        """Unicode compat helper
        """
        if sys.version < '3':
            return x + ''.decode("utf-8")
        else:
            return x

    @staticmethod
    def _color_string(string, color):
        """append color to a string + reset to white at the end of the string
        """
        if color is None:
            return string
        else:
            return color + string + '\033[0m'

    def _get_thresholds(self, data):
        """get various info (min, max, width... etc)
        from the data to graph.
        """
        all_thre = {}
        all_thre['value_max_length'] = 0
        all_thre['info_max_length'] = 0
        all_thre['max_pos_value'] = 0
        all_thre['min_neg_value'] = 0

        if self.max_value is not None:
            all_thre['max_pos_value'] = self.max_value

        # Iterate on all the items
        for (info, value, color) in data:
            totalvalue_len = 0

            # If we have a list of values for the item
            if isinstance(value, Iterable):
                icount = 0
                maxvalue = 0
                minvalue = 0
                for (ivalue, icolor) in value:
                    if ivalue < minvalue:
                        minvalue = ivalue
                    if ivalue > maxvalue:
                        maxvalue = ivalue
                    # if we are in multivalued mode, the value string is
                    # the concatenation of the values, separeted by a ',',
                    # len() must be computed on it
                    # if we are not in multivalued mode, len() is just the
                    # longer str(value) len ( /!\, value can be negative,
                    # which means that it's not simply len(str(max_value)))
                    if self.multivalue:
                        totalvalue_len += len("," + self._trans_hr(ivalue))
                    else:
                        totalvalue_len = max(totalvalue_len, len(self._trans_hr(ivalue)))

                if self.multivalue:
                    # remove one comma if multivalues
                    totalvalue_len = totalvalue_len - 1

            # If the item only has one value
            else:
                totalvalue_len = len(self._trans_hr(value))
                maxvalue = value
                minvalue = value

            if minvalue < all_thre['min_neg_value']:
                all_thre['min_neg_value'] = minvalue

            if maxvalue > all_thre['max_pos_value']:
                all_thre['max_pos_value'] = maxvalue

            if self._len_noansi(info) > all_thre['info_max_length']:
                all_thre['info_max_length'] = self._len_noansi(info)

            if totalvalue_len > all_thre['value_max_length']:
                all_thre['value_max_length'] = totalvalue_len

        return all_thre

    def _gen_graph_string(
            self, value, max_value, min_neg_value, graph_length, start_value_pos, color):
        """Generate the bar + its paddings (left and right)
        """
        def _gen_graph_string_part(
                value, max_value, min_neg_value, graph_length, color):

            all_width = max_value + abs(min_neg_value)

            if all_width == 0:
                bar_width = 0
            else:
                bar_width = int(abs(float(value)) * float(graph_length) / float(all_width))

            return (Pyasciigraph._color_string(
                    self.graphsymbol * bar_width,
                color),
                bar_width
                )

        all_width = max_value + abs(min_neg_value)

        if all_width == 0:
            bar_width = 0
            neg_width = 0
            pos_width = 0
        else:
            neg_width = int(abs(float(min_neg_value)) * float(graph_length) / float(all_width))
            pos_width = int(abs(max_value) * graph_length / all_width)

        if isinstance(value, Iterable):
            accuvalue = 0
            totalstring = ""
            totalsquares = 0

            sortedvalue = copy.deepcopy(value)
            sortedvalue.sort(reverse=False, key=lambda tup: tup[0])
            pos_value = [x for x in sortedvalue if x[0] >= 0]
            neg_value = [x for x in sortedvalue if x[0] < 0]

            # for the negative values, we build the bar + padding from 0 to the left
            for i in reversed(neg_value):
                ivalue = i[0]
                icolor = i[1]
                scaled_value = ivalue - accuvalue
                (partstr, squares) = _gen_graph_string_part(
                    scaled_value, max_value, min_neg_value, graph_length, icolor)
                totalstring = partstr + totalstring
                totalsquares += squares
                accuvalue += scaled_value

            # left padding
            totalstring = Pyasciigraph._u(' ') * (neg_width - abs(totalsquares)) + totalstring

            # reset some counters
            accuvalue = 0
            totalsquares = 0

            # for the positive values we build the bar from 0 to the right
            for i in pos_value:
                ivalue = i[0]
                icolor = i[1]
                scaled_value = ivalue - accuvalue
                (partstr, squares) = _gen_graph_string_part(
                    scaled_value, max_value, min_neg_value, graph_length, icolor)
                totalstring += partstr
                totalsquares += squares
                accuvalue += scaled_value

            # right padding
            totalstring += Pyasciigraph._u(' ') * (start_value_pos - neg_width - abs(totalsquares))
            return totalstring
        else:
            # handling for single value item
            (partstr, squares) = _gen_graph_string_part(
                value, max_value, min_neg_value, graph_length, color)
            if value >= 0:
                return Pyasciigraph._u(' ') * neg_width + \
                        partstr + \
                        Pyasciigraph._u(' ') * (start_value_pos - (neg_width + squares))
            else:
                return Pyasciigraph._u(' ') * (neg_width - squares) +\
                        partstr +\
                        Pyasciigraph._u(' ') * (start_value_pos - neg_width)


    def _gen_info_string(self, info, start_info_pos, line_length):
        """Generate the info string + padding
        """
        number_of_space = (line_length - start_info_pos - self._len_noansi(info))
        return info + Pyasciigraph._u(' ') * number_of_space

    def _gen_value_string(self, value, min_neg_value, color, start_value_pos, start_info_pos):
        """Generate the value string + padding
        """
        icount = 0
        if isinstance(value, Iterable) and self.multivalue:
            for (ivalue, icolor) in value:
                if icount == 0:
                    # total_len is needed because the color characters count
                    # with the len() function even when they are not printed to
                    # the screen.
                    totalvalue_len = len(self._trans_hr(ivalue))
                    totalvalue = Pyasciigraph._color_string(
                        self._trans_hr(ivalue), icolor)
                else:
                    totalvalue_len += len("," + self._trans_hr(ivalue))
                    totalvalue += "," + \
                        Pyasciigraph._color_string(
                            self._trans_hr(ivalue),
                            icolor)
                icount += 1
        elif isinstance(value, Iterable):
            max_value = min_neg_value
            color = None
            for (ivalue, icolor) in value:
                if ivalue > max_value:
                    max_value = ivalue
                    color = icolor
            totalvalue_len = len(self._trans_hr(max_value))
            totalvalue = Pyasciigraph._color_string(
                self._trans_hr(max_value), color)

        else:
            totalvalue_len = len(self._trans_hr(value))
            totalvalue = Pyasciigraph._color_string(
                self._trans_hr(value), color)

        number_space = start_info_pos -\
            start_value_pos -\
            totalvalue_len -\
            self.separator_length

        # This must not be negitive, this happens when the string length is
        # larger than the separator length
        if number_space < 0:
            number_space = 0

        return  ' ' * number_space + totalvalue +\
                ' ' * \
            ((start_info_pos - start_value_pos - totalvalue_len)
             - number_space)

    def _sanitize_string(self, string):
        """try to convert strings to UTF-8
        """
        # get the type of a unicode string
        unicode_type = type(Pyasciigraph._u('t'))
        input_type = type(string)
        if input_type is str:
            if sys.version < '3':
                info = unicode(string)
            else:
                info = string
        elif input_type is unicode_type:
            info = string
        elif input_type is int or input_type is float:
            if sys.version < '3':
                info = unicode(string)
            else:
                info = str(string)
        return info

    def _sanitize_value(self, value):
        """try to values to UTF-8
        """
        if isinstance(value, Iterable):
            newcollection = []
            for i in value:
                if len(i) == 1:
                    newcollection.append((i[0], None))
                elif len(i) >= 2:
                    newcollection.append((i[0], i[1]))
            return newcollection
        else:
            return value

    def _sanitize_data(self, data):
        ret = []
        for item in data:
            if (len(item) == 2):
                if isinstance(item[1], Iterable):
                    ret.append(
                        (self._sanitize_string(item[0]),
                         self._sanitize_value(item[1]),
                         None))
                else:
                    ret.append(
                        (self._sanitize_string(item[0]),
                         self._sanitize_value(item[1]),
                         None))
            if (len(item) == 3):
                ret.append(
                    (self._sanitize_string(item[0]),
                     self._sanitize_value(item[1]),
                     item[2]))
        return ret

    def graph(self, label=None, data=[]):
        """function generating the graph

        :param string label: the label of the graph
        :param iterable data: the data (list of tuple (info, value))
                info must be "castable" to a unicode string
                value must be an int or a float
        :rtype: a list of strings (each lines of the graph)

        """
        result = []
        san_data = self._sanitize_data(data)
        all_thre = self._get_thresholds(san_data)

        if not label is None:
            san_label = self._sanitize_string(label)
            label_len = self._len_noansi(san_label)
        else:
            label_len = 0

        real_line_length = max(self.line_length, label_len)

        min_line_length = self.min_graph_length +\
            2 * self.separator_length +\
            all_thre['value_max_length'] +\
            all_thre['info_max_length']

        if min_line_length < real_line_length:
            # calcul of where to start info
            start_info_pos = self.line_length -\
                all_thre['info_max_length']
            # calcul of where to start value
            start_value_pos = start_info_pos -\
                self.separator_length -\
                all_thre['value_max_length']
            # calcul of where to end graph
            graph_length = start_value_pos -\
                self.separator_length
        else:
            # calcul of where to start value
            start_value_pos = self.min_graph_length +\
                self.separator_length
            # calcul of where to start info
            start_info_pos = start_value_pos +\
                all_thre['value_max_length'] +\
                self.separator_length
            # calcul of where to end graph
            graph_length = start_value_pos -\
                self.separator_length
            # calcul of the real line length
            real_line_length = min_line_length

        if not label is None:
            result.append(san_label)
            result.append(Pyasciigraph._u(self.titlebar) * real_line_length)

        for info, value, color in san_data:

            graph_string = self._gen_graph_string(
                value,
                    all_thre['max_pos_value'],
                    all_thre['min_neg_value'],
                    graph_length,
                    start_value_pos,
                    color
            )

            value_string = self._gen_value_string(
                value,
                    all_thre['min_neg_value'],
                    color,
                    start_value_pos,
                    start_info_pos,
            )

            info_string = self._gen_info_string(
                info,
                    start_info_pos,
                    real_line_length
            )
            new_line = graph_string + value_string + info_string
            result.append(new_line)

        return result


class MetricBatchEmailNotifyOperator(BaseOperator):
    """
    Runs logic to package up and email anomalies.

    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

    def make_alert_lines(self, df_alert_metric, graph_symbol, anomaly_symbol, normal_symbol, alert_float_format):
            
            df_alert_metric = df_alert_metric.sort_values(by='metric_timestamp', ascending=False)
            x = df_alert_metric['metric_value'].round(2).values.tolist()
            labels = (
                np.where(
                  df_alert_metric['alert_status']==1,
                  anomaly_symbol,
                  normal_symbol
                ) 
                + (df_alert_metric['prob_anomaly_smooth'].round(2)*100).astype('int').astype('str') + '% ' 
                + df_alert_metric['metric_timestamp'].values
            ).to_list()
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
        alert_float_format = context['params'].get('alert_float_format','conditional')
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
