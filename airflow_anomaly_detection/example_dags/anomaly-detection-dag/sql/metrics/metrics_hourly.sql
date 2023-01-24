with

frontend_events as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'fe_pageviews_last1h' as metric_name,
  rand()*1000 as metric_value 
),

backend_events as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'be_events_last1h' as metric_name,
  rand()*1000 as metric_value 
),

metrics_hourly as
(
select * from frontend_events
union all
select * from backend_events
)

select
  metric_timestamp,
  'metrics_hourly' as metric_batch_name,
  metric_name,
  safe_cast(metric_value as float64) as metric_value 
from 
  metrics_hourly
;
