FROM python:3.11

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Set the working directory
WORKDIR /app

# Install system dependencies, including cron and openssl
RUN apt-get update && apt-get install -y \
    libglib2.0-dev \
    gcc \
    libc6-dev \
    libgpgme-dev \
    pkg-config \
    libdbus-1-dev \
    libsasl2-dev \
    python3-dev \
    libldap2-dev \
    libssl-dev \
    nginx \
    ca-certificates \
    cron \
    openssl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your application code
COPY . /app

# Copy the cron job
COPY crontab /etc/cron.d/my-cron
RUN sed -i 's/\r$//' /etc/cron.d/my-cron \
    && chmod 0644 /etc/cron.d/my-cron \
    && crontab /etc/cron.d/my-cron

# Copy the Nginx config file
# COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Create logs directory and set permissions
RUN mkdir -p /app/logs && chmod -R 777 /app/logs

# Create a directory for SSL certificates
# RUN mkdir -p /etc/nginx/ssl

# Copy SSL certificates into the container
# COPY certificates/server.crt /etc/nginx/ssl/server.crt
# COPY certificates/server.key /etc/nginx/ssl/server.key

# Expose ports for Nginx 443 for SSL
EXPOSE 80

# Start Nginx, Gunicorn, and cron
# CMD ["sh", "-c", "nginx && gunicorn --config gunicorn-cfg.py core.wsgi:application & python manage.py consume_notifications & cron -f"]

#CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:8000 & cron -f"]
CMD ["sh", "-c", "gunicorn --config gunicorn-cfg.py core.wsgi:application & python manage.py consume_notifications & cron -f"]


