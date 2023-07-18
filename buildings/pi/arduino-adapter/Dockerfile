FROM docker.io/library/python:3.10-buster

WORKDIR /app

COPY src/* .

RUN python -m pip install pip wheel --upgrade && \
    python -m pip install -r requirements.txt

CMD ["python", "controller.py"]