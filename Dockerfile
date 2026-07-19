FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install -r /app/backend/requirements.txt
COPY backend/app /app/backend/app
COPY frontend /app/frontend
WORKDIR /app/backend
ENV VALCLAIM_DATA_DIR=/data
EXPOSE 8765
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8765"]