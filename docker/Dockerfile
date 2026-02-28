FROM python:3.14
WORKDIR /app
COPY ./requirements.txt .
COPY ./app .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./docker/entrypoint.sh /tmp/entrypoint.sh
RUN chmod +x /tmp/entrypoint.sh
ENTRYPOINT ["bash", "-c", "/tmp/entrypoint.sh"]