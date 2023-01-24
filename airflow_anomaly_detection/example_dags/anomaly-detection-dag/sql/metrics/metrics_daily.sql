with

user_signups as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'user_signups_last24h' as metric_name,
  rand()*1000 as metric_value 
),

sales_revenue as
(
SELECT 
  timestamp('{{ ts }}') as metric_timestamp,
  'sales_revenue_last24h' as metric_name,
  rand()*1000 as metric_value 
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
