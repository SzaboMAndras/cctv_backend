# Base image
FROM python:3.10-slim

# Work folder
WORKDIR /app

# Dependencyk telepítése
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

# A lokális mappa másolása a konténerbe
COPY . .

# A konténeren belüli terminál megnyitása
CMD ["bash"]