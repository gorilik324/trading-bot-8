FROM ubuntu:18.04

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y software-properties-common && \
    echo "deb http://archive.ubuntu.com/ubuntu focal main universe" >> /etc/apt/sources.list && \
    echo "deb-src http://archive.ubuntu.com/ubuntu focal main universe" >> /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y libta-lib-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY app app

EXPOSE 7000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "7000"]
