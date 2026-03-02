FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY licensing/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copia o projeto inteiro (main.py importa licensing.*)
COPY licensing/ ./licensing/

# Entry point: uvicorn aponta para o módulo licensing.main
CMD ["sh", "-c", "uvicorn licensing.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
