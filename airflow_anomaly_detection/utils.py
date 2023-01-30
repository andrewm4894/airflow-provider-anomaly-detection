import os
import yaml

# TODO: clean these up they are horrible

def get_metric_batch_configs(config_dir):
    metric_batch_configs = [f'{config_dir}/{f}' for f in os.listdir(config_dir)]
    metric_batch_configs_yaml = [f for f in metric_batch_configs if f.endswith('.yaml')]
    metric_batch_configs_yaml_defaults = [f for f in metric_batch_configs_yaml if f.endswith('defaults.yaml')]
    metric_batch_configs_yaml_metric_batch = [f for f in metric_batch_configs_yaml if not f.endswith('defaults.yaml')]
    return metric_batch_configs_yaml_defaults, metric_batch_configs_yaml_metric_batch
