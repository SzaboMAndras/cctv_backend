# Base image
FROM python:3.10-slim

# Work folder
WORKDIR /app

# A lokális mappa másolása a konténerbe
COPY . .

# A konténeren belüli terminál megnyitása
CMD ["bash"]
