FROM ubuntu:22.04

RUN apt-get update && apt-get install -y gpiod python3 python3-pip

WORKDIR /app

#try to reduce layer cache invalidation when making updates
COPY src/requirements.txt .
RUN python3 -m pip install pip wheel --upgrade && \
    python3 -m pip install -r requirements.txt

COPY src/* .

CMD ["python3", "main.py"]