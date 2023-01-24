with

metric_batch_recency_ranked as
(
select 
  *,
  rank() over (partition by metric_name order by metric_timestamp desc) as metric_recency_rank  
from 
  `{{ params.gcp_destination_dataset }}.{{ params.gcp_ingest_destination_table_name }}`
where
  metric_batch_name = '{{ params.metric_batch_name }}'
  and
  metric_timestamp >= timestamp_sub(timestamp('{{ ts }}'), interval {{ params.max_n_days_ago }} day)
),

metric_batch_preprocessed_data as
(
select 
  metric_timestamp,
  metric_name,
  metric_recency_rank,
  {% for lag_n in range(params.preprocess_n_lags + 2) %}
  lag(metric_value, {{ lag_n }}) over (partition by metric_name order by metric_timestamp) as x_metric_value_lag{{ lag_n }},
  {% endfor %}
from 
  metric_batch_recency_ranked
)

select
  metric_timestamp,
  metric_name,
  {% for lag_n in range(params.preprocess_n_lags + 1) %}
  x_metric_value_lag{{ lag_n }} - x_metric_value_lag{{ lag_n + 1 }} as x_metric_value_lag{{ lag_n }}_diff,
  {% endfor %}
from 
  metric_batch_preprocessed_data
where
  {% for lag_n in range(params.preprocess_n_lags + 2) %}
  x_metric_value_lag{{ lag_n }} is not null
  and
  {% endfor %}
  metric_recency_rank <= {{ params.max_n }}
;
