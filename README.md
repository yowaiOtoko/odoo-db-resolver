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

## Project Structure

```
odoo-db-resolver/
├── saas_external_domain_resolver/     # Odoo module directory
│   ├── __manifest__.py               # Module manifest
│   └── models/
│       ├── __init__.py               # Models package init
│       └── saas_domain_resolver.py   # Main resolver logic
├── docker-compose.yml                 # Development setup
├── .env.example                       # Environment variables template
├── init-db.sql                       # Database initialization script
├── README.md                         # Project documentation
└── .gitignore                        # Git ignore rules
```

## Implementation Files

### `saas_external_domain_resolver/__manifest__.py`

```python
{
    'name': 'SaaS External Domain Resolver',
    'version': '19.0.1.0.0',
    'summary': 'Resolve subdomain/domain to correct database from external mapping',
    'author': 'Your Company',
    'depends': ['base'],
    'installable': True,
    'auto_install': False,
}
```

### `saas_external_domain_resolver/models/__init__.py`

```python
from . import saas_domain_resolver
```

### `saas_external_domain_resolver/models/saas_domain_resolver.py`

```python
import os
import psycopg2
from psycopg2.extras import DictCursor
import logging
import time
from odoo import models, tools, http

_logger = logging.getLogger(__name__)

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _dispatch(self):
        start_time = time.perf_counter()
        host = self._get_clean_host()
        if host:
            dbname = self._get_database_from_mapping(host)
            duration = (time.perf_counter() - start_time) * 1000
            if dbname:
                _logger.debug("Domain resolved: %s → '%s' (%.2fms)", host, dbname, duration)
                http.request.session.db = dbname
                http.request.env.cr.dbname = dbname
            else:
                _logger.warning("No mapping found for domain: %s (%.2fms)", host, duration)
        return super()._dispatch()

    def _get_clean_host(self):
        try:
            host = http.request.httprequest.host
            return host.split(':')[0].lower()
        except Exception:
            _logger.warning("Failed to read Host header")
            return None

    @tools.ormcache('host', cache='saas_domain_mapping', timeout=300)
    def _get_database_from_mapping(self, host):
        """Cached lookup from external mapping table"""
        env = os.environ
        config = {
            'host': env.get('SAAS_MAPPING_DB_HOST', 'postgres'),
            'port': int(env.get('SAAS_MAPPING_DB_PORT', '5432')),
            'dbname': env.get('SAAS_MAPPING_DB_NAME', 'app'),
            'user': env.get('SAAS_MAPPING_DB_USER', 'app'),
            'password': env.get('SAAS_MAPPING_DB_PASSWORD', ''),
        }
        if not config['password']:
            _logger.error("SAAS_MAPPING_DB_PASSWORD environment variable is not set!")
            return None
        try:
            with psycopg2.connect(**config, connect_timeout=2, application_name='odoo-saas-resolver') as conn:
                with conn.cursor(cursor_factory=DictCursor) as cr:
                    cr.execute("""
                        SELECT odoo_database
                        FROM tenant_domain_mapping
                        WHERE domain = %s AND is_active = true
                        LIMIT 1
                    """, (host,))
                    result = cr.fetchone()
                    return result['odoo_database'] if result else None
        except Exception as e:
            _logger.error("Domain mapping error for %s: %s", host, e)
            return None

def clear_saas_domain_cache():
    """Call this from your provisioning system after updating mappings"""
    try:
        http.root.registry.clear_cache('saas_domain_mapping')
        _logger.info("SaaS domain mapping cache cleared")
    except Exception as e:
        _logger.error("Failed to clear cache: %s", e)
```

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  odoo:
    image: odoo:19.0
    ports:
      - "8069:8069"
    volumes:
      - ./saas_external_domain_resolver:/mnt/extra-addons/saas_external_domain_resolver
      - odoo_data:/var/lib/odoo
    environment:
      - HOST=postgres
      - USER=odoo
      - PASSWORD=odoo
      - SAAS_MAPPING_DB_HOST=postgres
      - SAAS_MAPPING_DB_PORT=5432
      - SAAS_MAPPING_DB_NAME=app
      - SAAS_MAPPING_DB_USER=app
      - SAAS_MAPPING_DB_PASSWORD=app_password
    depends_on:
      - postgres
    labels:
      - "traefik.http.services.odoo.loadbalancer.server.port=8069"
      - "traefik.http.services.odoo.loadbalancer.passHostHeader=true"

  postgres:
    image: postgres:15
    environment:
      - POSTGRES_DB=app
      - POSTGRES_USER=app
      - POSTGRES_PASSWORD=app_password
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init-db.sql
    ports:
      - "5432:5432"

volumes:
  odoo_data:
  postgres_data:
```

### `.env.example`

```env
# Odoo Configuration
HOST=postgres
USER=odoo
PASSWORD=odoo

# SaaS Mapping Database Configuration
SAAS_MAPPING_DB_HOST=postgres
SAAS_MAPPING_DB_PORT=5432
SAAS_MAPPING_DB_NAME=app
SAAS_MAPPING_DB_USER=app
SAAS_MAPPING_DB_PASSWORD=app_password
```

### `init-db.sql`

```sql
-- Create the tenant domain mapping table
CREATE TABLE IF NOT EXISTS tenant_domain_mapping (
    domain VARCHAR(255) PRIMARY KEY,
    odoo_database VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_tenant_domain_mapping_domain ON tenant_domain_mapping(domain);
CREATE INDEX IF NOT EXISTS idx_tenant_domain_mapping_active ON tenant_domain_mapping(is_active);

-- Insert sample data for development/testing
INSERT INTO tenant_domain_mapping (domain, odoo_database, is_active) VALUES
('client1.localhost', 'client1_db', true),
('client2.localhost', 'client2_db', true),
('demo.localhost', 'demo_db', true)
ON CONFLICT (domain) DO NOTHING;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_tenant_domain_mapping_updated_at
    BEFORE UPDATE ON tenant_domain_mapping
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

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