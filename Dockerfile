FROM docker.io/bitnami/python:3.10.3-debian-10-r38

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY app app

EXPOSE 7000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "7000"]
