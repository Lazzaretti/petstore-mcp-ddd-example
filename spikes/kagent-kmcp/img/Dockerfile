FROM python:3.12-slim
RUN pip install --no-cache-dir fastmcp==4.1.4 uvicorn
WORKDIR /app
COPY app.py sales_only.py ./
EXPOSE 8000
CMD ["uvicorn", "sales_only:app", "--host", "0.0.0.0", "--port", "8000"]
