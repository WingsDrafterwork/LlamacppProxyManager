# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Set environment variables
ENV LLAMA_CPP_BASE_URL=<your_base_url>
ENV LLAMA_CPP_API_KEY=<your_api_key>
ENV PORT=8001

# Set the working directory
WORKDIR /app

# Copy requirements.txt and install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY background_queue.py ./
COPY background_api.py ./
COPY main.py ./

# Expose port 8001
EXPOSE 8001

# Command to run the application
CMD ["python", "main.py"]