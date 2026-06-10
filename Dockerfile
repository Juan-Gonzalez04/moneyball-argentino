FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
postgresql-client \
&& rm -rf /var/lib/apt/lists/*

# Copiar requirements
COPY requirements.txt .

# Instalar Python deps
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY scripts/ scripts/
COPY sql/ sql/
# COPY config/ config/

# Por defecto, no hacer nada (override con docker-compose)
CMD ["bash"] 
