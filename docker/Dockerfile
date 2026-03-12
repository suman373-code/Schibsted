FROM apache/airflow:2.8.1-python3.11

# Install the Python packages our pipeline needs
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
