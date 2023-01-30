import os


def get_metric_batch_configs(config_dir):
    metric_batch_configs = [f'{config_dir}/{f}' for _, _, files in os.walk(config_dir) for f in files]
    metric_batch_configs = [f for f in metric_batch_configs if f.endswith('.yaml')]
    metric_batch_configs = [f for f in metric_batch_configs if not f.endswith('defaults.yaml')]
    return metric_batch_configs
