import psycopg2
from psycopg2.extras import DictCursor
import logging
import os

_logger = logging.getLogger('odoo.addons.saas_external_domain_resolver.middleware')


def _get_database_from_mapping(host):
    env = os.environ
    password = env.get('SAAS_MAPPING_DB_PASSWORD', '')
    if not password:
        _logger.error("SaaS resolver: SAAS_MAPPING_DB_PASSWORD not set")
        return None
    config = {
        'host': env.get('SAAS_MAPPING_DB_HOST', 'localhost'),
        'port': int(env.get('SAAS_MAPPING_DB_PORT', '5432')),
        'dbname': env.get('SAAS_MAPPING_DB_NAME', 'domains'),
        'user': env.get('SAAS_MAPPING_DB_USER', 'postgres'),
        'password': password,
    }
    try:
        with psycopg2.connect(**config, connect_timeout=2) as conn:
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
        _logger.error("SaaS resolver DB error for %s: %s", host, e)
        return None


def post_load():
    """Patch Odoo's db_filter to resolve tenant DB from external mapping.
    This avoids any session/CSRF manipulation — Odoo selects the DB naturally."""
    import odoo.http as http_module

    original_db_filter = http_module.db_filter

    def patched_db_filter(dbs, host=None):
        resolved_host = None
        if host is not None:
            if isinstance(host, str):
                # Odoo 19: db_filter(dbs, host=hostname_string)
                resolved_host = host.split(':')[0].lower()
            elif hasattr(host, 'environ'):
                # older calling convention: db_filter(dbs, httprequest)
                resolved_host = (host.environ.get('HTTP_HOST', '') or '').split(':')[0].lower()
        if resolved_host:
            dbname = _get_database_from_mapping(resolved_host)
            if dbname:
                _logger.info("SaaS resolver: %s → '%s'", resolved_host, dbname)
                return [dbname]
        return original_db_filter(dbs, host)

    http_module.db_filter = patched_db_filter
    _logger.info("SaaS resolver: db_filter patched")