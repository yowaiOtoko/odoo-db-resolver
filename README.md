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
