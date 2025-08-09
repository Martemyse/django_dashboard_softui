### Django Overview Applications (Sanitized Showcase)

This repository contains a production-style Django project demonstrating:
- Multi-app setup with role-based access and dynamic navigation
- Notifications with optional RabbitMQ integration
- External reporting database connectivity
- Docker-friendly, environment-driven configuration

### Tech Stack
- Backend: Django, Django REST Framework, custom auth backends, management commands, migrations
- Realtime/Messaging: RabbitMQ (pika), queue-per-token fanout pattern for notifications
- Databases: PostgreSQL (primary), optional external reporting DB via SQLAlchemy
- Frontend: HTMX for partial updates, Alpine.js for light interactivity, Bootstrap 5/Soft-UI styling
- JS/Build: Vanilla JS modules, minimal tooling; React example artifact included for config UI exploration
- Ops/Runtime: Docker, docker-compose, gunicorn, environment-based settings, Render blueprint (optional)
- Utilities: Pandas/Numpy for data shaping, schedule/cron via management commands and `crontab`

All secrets, emails, hostnames, IPs, and organization-specific details have been removed or parameterized via environment variables.

### Quick Start
1) Copy `.env.example` to `.env` and adjust values as needed.
2) Install dependencies: `pip install -r requirements.txt`.
3) Apply migrations and run the server.

Optional:
- Enable RabbitMQ by setting `RABBITMQ_*` vars in `.env`.
- Configure external reporting DB via `EXTERNAL_DATABASE_URL`.

### Configuration
Env vars control everything, including:
- `DEBUG`, `DEVELOPMENT`, `SECRET_KEY`, `ALLOWED_HOSTS`
- Primary DB: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`
- External DB: `EXTERNAL_DATABASE_URL` or (`EXTERNAL_DB_*`)
- Email: `DEFAULT_FROM_EMAIL`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- RabbitMQ: `RABBITMQ_HOST`, `RABBITMQ_PORT`, `RABBITMQ_USERNAME`, `RABBITMQ_PASSWORD`

### Apps
- `home/` – authentication, permissions, notifications
- `pregled_aktivnosti/` – activity overview
- `signali_strojev/` – machine signals and reporting
- `vgradni_deli/` – components module

### Notable Features
- HTMX endpoints and fragments for dynamic UI updates without heavy SPA overhead
- Alpine.js bindings for small interactive states/components
- Role-to-permission mapping per app/department (role groups) with management UI
- RabbitMQ integration for one-to-one terminal/user notifications with durable exchanges
- External analytics queries via SQLAlchemy engine pools
- Custom `manage.py` commands for database bootstrap, demo data, and background tasks

### Demo Data
See `home/management/commands/manage_database.py` for demo helpers. Values are sanitized and rely on env vars.

### License
Contains third-party UI assets; review respective licenses before commercial use.
