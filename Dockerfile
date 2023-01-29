FROM apache/airflow:2.5.0

COPY requirements.txt /
RUN pip install --no-cache-dir -r /requirements.txt

# docker compose mounts instead
#RUN pip install --no-cache-dir airflow-provider-anomaly-detection==0.0.15
#COPY airflow_anomaly_detection/ .
#ENV AIRFLOW__CORE__DAGS_FOLDER=/opt/airflow/example_dags
