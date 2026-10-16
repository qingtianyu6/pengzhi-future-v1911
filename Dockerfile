FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN NODE_OPTIONS=--max-old-space-size=2048 npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8000
WORKDIR /app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://mirrors.tencentyun.com/pypi/simple 'torch==2.13.0+cpu' 'torchvision==0.28.0+cpu'
RUN pip install --no-cache-dir --index-url https://mirrors.tencentyun.com/pypi/simple -r /app/backend/requirements.txt

COPY backend/ /app/backend/
COPY --from=frontend-build /app/frontend/dist /app/frontend/dist
RUN mkdir -p /app/backend/data /app/backend/uploads

WORKDIR /app/backend
EXPOSE 8000
CMD ["python", "run.py"]
