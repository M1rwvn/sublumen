FROM node:20-slim AS ui
WORKDIR /ui
COPY frontend-react/package.json ./
RUN npm install
COPY frontend-react/ ./
RUN npx vite build

FROM python:3.10-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/
COPY --from=ui /ui/dist /app/frontend-react/dist
COPY docs/ /app/docs/
WORKDIR /app/backend
RUN useradd -m -u 10001 sublumen && mkdir /data && chown sublumen /data
USER 10001
ENV SS_DATA=/data
EXPOSE 5000
HEALTHCHECK CMD ["python","-c","import urllib.request;urllib.request.urlopen('http://localhost:5000/api/health')"]
CMD ["gunicorn","-b","0.0.0.0:5000","-w","2","wsgi:app"]
