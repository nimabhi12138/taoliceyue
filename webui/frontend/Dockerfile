FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir streamlit==1.38.0 requests==2.32.3 PyYAML==6.0.2
COPY app.py .
EXPOSE 8501
ENV PYTHONUNBUFFERED=1
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]