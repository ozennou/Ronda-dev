FROM python:3.9.21-slim-bullseye

COPY . /app

WORKDIR /app

RUN pip install --upgrade pip

RUN pip install -r Requirements.txt

RUN chmod +x /app/script.sh

ENTRYPOINT ["/app/script.sh"]