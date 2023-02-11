/*

This example query generates a batch of metrics for the last hour.
The metrics are generated randomly.

The outputs of the query must be in the following format:
- metric_timestamp: The timestamp of the metric.
- metric_batch_name: The name of the batch of metrics.
- metric_name: The name of the metric.
- metric_value: The value of the metric.

*/

with

frontend_events as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'fe_pageviews_last1h' as metric_name,
  if(rand()>=0.95,rand()*10000,rand()*1000) as metric_value 
),

backend_events as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'be_events_last1h' as metric_name,
  if(rand()>=0.90,rand()*10,rand()*1000) as metric_value 
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
  ifnull(safe_cast(metric_value as float64),0.0) as metric_value 
from 
  metrics_hourly
;
