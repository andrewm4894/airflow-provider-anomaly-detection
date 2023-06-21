/*

This query is used to preprocess the data before it is used for training the model 
and during scoring using the trained model. Any cols starting with "x_" will be used
as features for training and scoring.

The output needs to be a table with the following columns:
- metric_timestamp
- metric_name
- metric_value
- x_... (features)

*/

with

metric_batch_recency_ranked as
(
select 
  *,
  rank() over (partition by metric_name order by metric_timestamp desc) as metric_recency_rank,
  max(metric_timestamp) over (partition by metric_name) as metric_timestamp_max
from 
  `{{ params.gcp_destination_dataset }}.{{ params.gcp_ingest_destination_table_name }}`
where
  metric_batch_name = '{{ params.metric_batch_name }}'
  and
  -- limit the data to the last {{ params.max_n_days_ago }} days for efficiency
  metric_timestamp >= timestamp_sub(timestamp('{{ ts }}'), interval {{ params.max_n_days_ago }} day)
),

metric_batch_preprocessed_data as
(
select 
  metric_timestamp,
  metric_name,
  metric_value,
  metric_recency_rank,
  -- calculate the number of hours since the metric was last updated
  timestamp_diff(current_timestamp(), metric_timestamp_max, hour) as metric_last_updated_hours_ago,  
  -- x_... features
  -- lag the metric value by 0, 1, 2, ..., {{ params.preprocess_n_lags }}
  {% for lag_n in range(params.preprocess_n_lags + 2) %}
  lag(metric_value, {{ lag_n }}) over (partition by metric_name order by metric_timestamp) as x_metric_value_lag{{ lag_n }},
  {% endfor %}
  -- one-hot encode the hour of the day
  {% for hour_n in range(24) %}
  if(extract(hour from metric_timestamp)={{ hour_n }},1,0) as x_hour_is_{{ hour_n }},
  {% endfor %}
  -- one-hot encode the dayofweek
  {% for dayofweek_n in range(7) %}
  if(extract(dayofweek from metric_timestamp)={{ dayofweek_n }},1,0) as x_dayofweek_is_{{ dayofweek_n }},
  {% endfor %}
from 
  metric_batch_recency_ranked
)

select
  metric_timestamp,
  metric_name,
  metric_value,
  -- x_... features
  -- take difference between the metric value and the lagged metric value
  {% for lag_n in range(params.preprocess_n_lags + 1) %}
  x_metric_value_lag{{ lag_n }} - x_metric_value_lag{{ lag_n + 1 }} as x_metric_value_lag{{ lag_n }}_diff,
  {% endfor %}
  {% for hour_n in range(24) %}
  x_hour_is_{{ hour_n }},
  {% endfor %}
  {% for dayofweek_n in range(7) %}
  x_dayofweek_is_{{ dayofweek_n }},
  {% endfor %}
from 
  metric_batch_preprocessed_data
where
  -- limit to non-null feature vectors
  {% for lag_n in range(params.preprocess_n_lags + 2) %}
  x_metric_value_lag{{ lag_n }} is not null
  and
  {% endfor %}
  -- limit to the last {{ params.max_n }} rows which will be used for training and scoring
  metric_recency_rank <= {{ params.max_n }}
  and
  -- only include metrics last updated less than {{ params.metric_last_updated_hours_ago_max }} hours ago
  metric_last_updated_hours_ago <= {{ params.metric_last_updated_hours_ago_max }}
;
