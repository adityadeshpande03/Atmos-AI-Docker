FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create directory structure
RUN mkdir -p /app/frontend /app/src

# Copy application files
COPY src/ /app/src/
COPY frontend/ /app/frontend/

# Set environment variables
ENV MONGODB_URI="mongodb+srv://adityadeshpande03:Predator1734@atmosai.ghtdw.mongodb.net/?retryWrites=true&w=majority&appName=AtmosAI"
ENV GROQ_API_KEY="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"

# Make start script executable
COPY start.sh .
RUN chmod +x start.sh

EXPOSE 8000 8080

CMD ["./start.sh"]
