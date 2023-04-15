FROM python:3.10

WORKDIR /app

RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y software-properties-common && \
    add-apt-repository universe && \
    apt-get update && \
    apt-get install -y libta-lib-dev

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY app app

EXPOSE 7000

CMD ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "7000"]
