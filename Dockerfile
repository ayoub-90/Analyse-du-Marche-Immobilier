FROM apache/airflow:2.7.3-python3.10

USER root
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && apt-get clean

USER airflow
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt