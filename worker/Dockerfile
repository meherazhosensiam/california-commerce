FROM python:3.12-slim
RUN pip install --no-cache-dir redis==5.2.1
COPY worker.py /worker.py
CMD ["python","/worker.py"]
