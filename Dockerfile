FROM python:3.10

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y software-properties-common && \
    sed -i 's/^#\s*\(deb.*universe\)$/\1/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y libta-lib-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip

RUN pip install -r requirements.txt

COPY app app

EXPOSE 7000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "7000"]
