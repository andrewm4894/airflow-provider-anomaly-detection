/*

This query generates a batch of metrics for the metrics_daily batch.
The metrics are generated randomly, but the query can be modified to
pull metrics from a data warehouse or other data source.

The outputs of the query must be in the following format:
- metric_timestamp: The timestamp of the metric.
- metric_batch_name: The name of the batch of metrics.
- metric_name: The name of the metric.
- metric_value: The value of the metric.

*/

with

user_signups as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'user_signups_last24h' as metric_name,
  if(rand()>=0.90,rand()*10,rand()*1000) as metric_value  
),

sales_revenue as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'sales_revenue_last24h' as metric_name,
  if(rand()>=0.99,rand()*10000,rand()*1000) as metric_value 
),

metrics_daily as
(
select * from user_signups
union all
select * from sales_revenue
)

select
  metric_timestamp,
  'metrics_daily' as metric_batch_name,
  metric_name,
  safe_cast(metric_value as float64) as metric_value 
from 
  metrics_daily
;
