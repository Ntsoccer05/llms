FROM python:3.14
WORKDIR /app
COPY ./requirements.txt .
COPY ./app .

RUN pip install --no-cache-dir -r requirements.txt

COPY ./docker/entrypoint.sh /tmp/entrypoint.sh
RUN sed -i 's/\r$//' /tmp/entrypoint.sh && chmod +x /tmp/entrypoint.sh
ENTRYPOINT ["/tmp/entrypoint.sh"]