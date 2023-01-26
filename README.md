# Anomaly Detection with Apache Airflow

Painless anomaly detection (using [PyOD](https://github.com/yzhao062/pyod)) with Apache Airflow.

How it works in a nutshell:
1. Create and express your metrics via SQL queries.
1. Some YAML configuration fun.
1. Receive useful alerts when metrics look anomalous.

## Example Alert

Example output of an alert. Horizontal bar chart used to show metric values over time. 
Smoothed anomaly score is shown as a `%` and any flagged anomalies are marked with `*`.

Below is the sql to pull the metric in question for investigation.

### Alert Text (ascii art yay!)

```
🤷 [some_metric_last1h] looks anomalous (2023-01-25 16:00:00) 🤷
```
```
some_metric_last1h (2023-01-24 15:30:00 to 2023-01-25 16:00:00)
                                                                                       
t=0   ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,742.00    72% 2023-01-25 16:00:00
t=-1  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~       3,165.00  * 81% 2023-01-25 15:30:00
t=-2  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  3,448.00  * 95% 2023-01-25 15:15:00
t=-3  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~   3,441.00    76% 2023-01-25 15:00:00
t=-4  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                 2,475.00    72% 2023-01-25 14:30:00
t=-5  ~~~~~~~~~~~~~~~~~~~~~~~~~~                          1,833.00    72% 2023-01-25 14:15:00
t=-6  ~~~~~~~~~~~~~~~~~~~~                                1,406.00    72% 2023-01-25 14:00:00
t=-7  ~~~~~~~~~~~~~~~~~~~                                 1,327.00  * 89% 2023-01-25 13:30:00
t=-8  ~~~~~~~~~~~~~~~~~~~                                 1,363.00    78% 2023-01-25 13:15:00
t=-9  ~~~~~~~~~~~~~~~~~~~~~~~~                            1,656.00    66% 2023-01-25 13:00:00
t=-10 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                      2,133.00    51% 2023-01-25 12:30:00
t=-11 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                  2,392.00    40% 2023-01-25 12:15:00
t=-12 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                2,509.00    41% 2023-01-25 12:00:00
t=-13 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,729.00    42% 2023-01-25 11:30:00
t=-14 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,696.00    44% 2023-01-25 11:15:00
t=-15 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~               2,618.00    41% 2023-01-25 11:00:00
t=-16 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                  2,390.00    39% 2023-01-25 10:30:00
t=-17 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~               2,601.00    27% 2023-01-24 20:00:00
t=-18 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~           2,833.00    25% 2023-01-24 17:30:00
t=-19 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~          2,910.00    28% 2023-01-24 17:15:00
t=-20 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,757.00    22% 2023-01-24 17:00:00
t=-21 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,696.00    34% 2023-01-24 16:30:00
t=-22 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~              2,651.00    37% 2023-01-24 16:15:00
t=-23 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~            2,797.00    39% 2023-01-24 16:00:00
t=-24 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~             2,739.00    40% 2023-01-24 15:30:00

```
```sql
select *
from `metrics.metrics` m
join `metrics.metrics_scored` s
on m.metric_name = s.metric_name and m.metric_timestamp = s.metric_timestamp
where m.metric_name = 'some_metric_last1h'
order by m.metric_timestamp desc
```

### Alert Chart

A slightly more fancy chart is also attached to alert emails. The top line graph shows the metric values over time. The bottom line graph shows the smoothed anomaly score over time along with the alert status for any flagged anomalies where the smoothed anomaly score passes the threshold.

![alert-chart-example](/img/alert-chart-example.png)

## Getting Started

Check out the [example dag](https://github.com/andrewm4894/airflow-provider-anomaly-detection/tree/main/airflow_anomaly_detection/example_dags/anomaly-detection-dag/) to get started.

### Prerequisites

* Currently only Google BiqQuery is supported as a data source. The plan is to add Snowflake next and then probably Redshift. PR's to add other data sources are very welcome (some refactoring probably needed).

### Installation

Install from [PyPI](https://pypi.org/project/airflow-provider-anomaly-detection/) as usual.

```bash
pip install airflow-provider-anomaly-detection
```

### Configuration

See the example configuration files in the [example dag](https://github.com/andrewm4894/airflow-provider-anomaly-detection/tree/main/airflow_anomaly_detection/example_dags/anomaly-detection-dag/config/) folder. You can use a `defaults.yaml` or specific `<metric-batch>.yaml` for each metric batch if needed.
