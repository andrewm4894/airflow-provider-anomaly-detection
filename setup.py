"""Setup.py for the Anomaly Detection Airflow provider package."""

from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

"""Perform the package airflow-provider-anomaly-detection setup."""
setup(
    name='airflow-provider-anomaly-detection',
    version="0.0.1",
    description='An airflow provider for anomaly detection.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    entry_points={
        "apache_airflow_provider": [
            "provider_info=anomaly_detection.__init__:get_provider_info"
        ]
    },
    license='Apache License 2.0',
    packages=['anomaly_detection', 'anomaly_detection.operators'],
    install_requires=['apache-airflow>=2.0'],
    setup_requires=['setuptools', 'wheel'],
    author='Andrew Maguire',
    author_email='andrewm4894@gmail.com',
    url='https://github.com/andrewm4894/airflow-provider-anomaly-detection',
    classifiers=[
        "Framework :: Apache Airflow",
        "Framework :: Apache Airflow :: Provider",
    ],
    python_requires='~=3.7',
)
