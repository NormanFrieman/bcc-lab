FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir mysql-connector-python

COPY workload.py .

CMD ["python", "-u", "workload.py"]
