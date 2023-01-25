import os
import yaml

# TODO: clean these up they are horrible

def get_metric_batch_configs(config_dir):
    metric_batch_configs = [f'{config_dir}/{f}' for f in os.listdir(config_dir)]
    metric_batch_configs = [f for f in metric_batch_configs if f.endswith('.yaml') and not f.endswith('defaults.yaml')]
    return metric_batch_configs


def get_metric_batch_config_defaults(config_dir):
    metric_batch_configs_defaults = [f'{config_dir}/{f}' for f in os.listdir(config_dir)]
    metric_batch_configs_defaults = [f for f in metric_batch_configs_defaults if f.endswith('defaults.yaml')]
    for metric_batch_config_file in metric_batch_configs_defaults:
        with open(metric_batch_config_file) as yaml_file:
            metric_batch_config_defaults = yaml.safe_load(yaml_file)
    return metric_batch_config_defaults