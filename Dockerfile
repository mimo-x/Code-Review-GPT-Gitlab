FROM python:3.9-slim

RUN apt-get update && apt-get install -y gcc libffi-dev python3-dev

WORKDIR /workspace

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/workspace

CMD ["python", "app.py"]


