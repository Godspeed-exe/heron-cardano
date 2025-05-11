FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy entire project
COPY . /app

# Expose the port FastAPI will run on
EXPOSE 8000

# Default command
CMD ["uvicorn", "heron_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
