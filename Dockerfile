FROM python:3.13-slim
 
# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    apt-transport-https \
    lsb-release \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Set Azure environment variables
ENV AZURE_CLIENT_ID="87cdd501-eff1-4190-a7de-579e8ceb4611"
ENV AZURE_TENANT_ID="89cf11d4-079d-47a6-af93-e6ae64ceb42c"
ENV AZURE_CLIENT_SECRET="hI38Q~WENTyTMvsQHveBq0_FiWhxIqKlG8nWYai6"
 
# Install Azure CLI
RUN curl -sL https://aka.ms/InstallAzureCLIDeb | bash
 
# Install Azure CLI dependencies
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*
 
# Add Azure CLI to PATH
ENV PATH="/usr/local/sdk/azure-cli:$PATH"
 
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Set working directory
WORKDIR /
 
# Copy application code
COPY . .
 
# Expose port
EXPOSE 5000
 
 
# Command to run the application
CMD ["python", "app.py"]
 