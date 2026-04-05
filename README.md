# SaaS Domain-to-Database Resolver for Odoo 19

This Odoo module enables SaaS functionality by automatically resolving subdomains to the correct database using an external PostgreSQL mapping table.

## Overview

Each client accesses Odoo via a unique subdomain (e.g. `client1.odoo.invo-facturation.fr`), and Odoo automatically connects to the correct database based on a mapping stored in an external PostgreSQL database.

## Architecture

- **Frontend**: Custom subdomains (e.g. `client1.odoo.invo-facturation.fr`)
- **Reverse Proxy**: Traefik (Dokploy)
- **Odoo 19**: Single Odoo instance running in shared/multi-database mode
- **Mapping Database**: External PostgreSQL database (`tenant_domain_mapping` table)
- **Resolver**: Lightweight Odoo module that runs on every request

## Installation

1. Copy the `saas_external_domain_resolver` folder to your Odoo addons directory
2. Install the module through Odoo interface or use `-i saas_external_domain_resolver`

## Configuration

### Environment Variables

Add these environment variables to your Odoo container:

```env
SAAS_MAPPING_DB_HOST=your-postgres-host
SAAS_MAPPING_DB_PORT=5432
SAAS_MAPPING_DB_NAME=your-database-name
SAAS_MAPPING_DB_USER=your-username
SAAS_MAPPING_DB_PASSWORD=your-password
```

### Traefik Configuration

Ensure your Traefik configuration includes:

```yaml
- "traefik.http.services.odoo.loadbalancer.server.port=8069"
- "traefik.http.services.odoo.loadbalancer.passHostHeader=true"
```

### Odoo Configuration

Add to your Odoo config file:

```ini
log_handler = odoo.addons.saas_external_domain_resolver:DEBUG
```

## Database Schema

The external mapping table should have the following structure:

```sql
CREATE TABLE tenant_domain_mapping (
    domain VARCHAR(255) PRIMARY KEY,
    odoo_database VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true
);
```

## Usage

1. Set up your domain mappings in the external database
2. Configure DNS to point subdomains to your Traefik/Odoo instance
3. Access Odoo via subdomains - the module will automatically route to the correct database

## Development

### Running with Docker

1. Copy `.env.example` to `.env` and configure your settings
2. Run `docker-compose up -d`
3. Access Odoo at `http://localhost:8069`

### Cache Management

After updating domain mappings, call the cache clearing function:

```python
from odoo.addons.saas_external_domain_resolver.models.saas_domain_resolver import clear_saas_domain_cache
clear_saas_domain_cache()
```

## Performance

- Domain lookups are cached for 300 seconds (5 minutes)
- External database connections use connection pooling
- Connection timeout is set to 2 seconds for fast failure

## Security

- Only active mappings are considered
- Invalid domains are logged as warnings
- Database credentials are read from environment variables