/*
This query is used to generate the alert status for each metric in the last {{ params.alert_max_n }} days.
The alert status is a binary flag indicating whether the metric is anomalous or not.

The alert status is calculated as follows:
- For each metric, calculate the smoothed probability of anomaly using a moving average window of {{ params.alert_smooth_n }} days.
- If the smoothed probability of anomaly is greater than or equal to {{ params.alert_status_threshold }}, then the alert status is 1, otherwise it is 0.
*/

with

metrics_scored_recency_ranked as
(
select 
  metrics.metric_timestamp,
  metrics.metric_batch_name,
  metrics.metric_name, 
  metrics.metric_value,
  avg(metrics_scored.prob_anomaly) as prob_anomaly,
  rank() over (partition by metrics.metric_name order by metrics.metric_timestamp desc) as metric_recency_rank
from 
  `{{ params.gcp_destination_dataset }}.{{ params.gcp_ingest_destination_table_name }}` metrics
join
  `{{ params.gcp_destination_dataset }}.{{ params.gcp_score_destination_table_name }}` metrics_scored
on 
  metrics.metric_name = metrics_scored.metric_name
  and
  metrics.metric_timestamp = metrics_scored.metric_timestamp
where
  metrics.metric_batch_name = '{{ params.metric_batch_name }}'
  and
  metrics_scored.metric_timestamp >= timestamp_sub(timestamp('{{ ts }}'), interval {{ params.max_n_days_ago }} day)
group by 1,2,3,4
),

metrics_scored_smooth as
(
select 
  *,
  avg(prob_anomaly) over (partition by metric_name order by metric_recency_rank desc RANGE BETWEEN {{ params.alert_smooth_n }} PRECEDING AND CURRENT ROW) as prob_anomaly_smooth
from 
  metrics_scored_recency_ranked
),

metrics_alert_flags as
(
select 
  *,
  case
    when prob_anomaly_smooth >= {{ params.alert_status_threshold }} then 1
    else 0 
  end as alert_status 
from 
  metrics_scored_smooth
),

metrics_alert_flagged as
(
select
  *,
  max(alert_status) over (partition by metric_name) as has_alert_in_max_n
from
  metrics_alert_flags
where
  metric_recency_rank <= {{ params.alert_max_n }}
),

metrics_alert_window_flagged as
(
select
  metric_name,
  max(alert_status) as has_alert_in_window_last_n
from
  metrics_alert_flagged
where
  metric_recency_rank <= {{ params.alert_window_last_n }}
group by 1
)

select
  metrics_alert_flagged.metric_timestamp,
  metric_batch_name,
  metrics_alert_flagged.metric_name,
  metric_value,
  prob_anomaly_smooth,
  alert_status,
from 
  metrics_alert_flagged
left outer join
  metrics_alert_window_flagged
on
  metrics_alert_flagged.metric_name = metrics_alert_window_flagged.metric_name
where
  has_alert_in_window_last_n = 1
order by 
  metric_name, metric_timestamp
;
