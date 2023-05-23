# Anomaly Gallery

Some interesting real world anomalies from various business metrics.

**Note**: May need to right click and open image in new tab to see them properly.

- [`bump_and_spike_example`](/anomaly_gallery/bump_and_spike_example.jpg): Nice example with both a spread out bump and a spike.
- [`etl_delay_example`](/anomaly_gallery/etl_delay_example.jpg): Example where a regular ETL process changes unexpectedly. The metric in this case was minutes since table was last updated, the anomaly was the regular update schedule being missed.
- [`increasing_table_row_count_then_sudden_drop`](/anomaly_gallery/increasing_table_row_count_then_sudden_drop.jpg): This was metric of row counts on a table expected to keep increasing over time. The anomaly was a sudden drop in row count. This was related to some backend cleaning scripts that were run but turned out very important to catch/understand when interpreting the data.
- [`saw_tooth_example`](/anomaly_gallery/saw_tooth_example.jpg): Example of some increased variability leading to a "saw tooth" pattern.
- [`sharp_drop_example`](/anomaly_gallery/sharp_drop_example.jpg): Example with a sharp drop leading to an anomaly.
