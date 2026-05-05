import psycopg2
from psycopg2.extras import DictCursor
import logging
import os

_logger = logging.getLogger('odoo.addons.saas_external_domain_resolver.middleware')


def _init_sentry():
    dsn = os.environ.get('ODOO_ADDON_SENTRY_DSN', '')
    if not dsn:
        return
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=dsn,
            send_default_pii=True,
            enable_logs=True,
            environment=os.environ.get('ODOO_ADDON_RUNNING_ENV', 'production'),
            release=os.environ.get('SENTRY_RELEASE', None),
        )
        _logger.info("SaaS resolver: Sentry initialized")
    except ImportError:
        _logger.warning("SaaS resolver: sentry-sdk not installed, skipping Sentry init")
    except Exception as e:
        _logger.warning("SaaS resolver: Sentry init failed: %s", e)


def _capture_exception(exc):
    try:
        import sentry_sdk
        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


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
    _logger.info(
        "SaaS resolver: mapping lookup host=%s via %s:%s/%s user=%s",
        host,
        config['host'],
        config['port'],
        config['dbname'],
        config['user'],
    )
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
                if result:
                    _logger.info("SaaS resolver: mapping hit host=%s db=%s", host, result['odoo_database'])
                    return result['odoo_database']
                _logger.warning("SaaS resolver: mapping miss host=%s", host)
                return None
    except Exception as e:
        _logger.error("SaaS resolver DB error for %s: %s", host, e)
        _capture_exception(e)
        return None


def post_load():
    """Patch Odoo's db_filter to resolve tenant DB from external mapping.
    This avoids any session/CSRF manipulation — Odoo selects the DB naturally."""
    _init_sentry()
    import odoo.http as http_module

    original_db_filter = http_module.db_filter

    def patched_db_filter(dbs, host=None):
        resolved_host = None
        host_type = type(host).__name__ if host is not None else 'None'
        if host is not None:
            if isinstance(host, str):
                # Odoo 19: db_filter(dbs, host=hostname_string)
                resolved_host = host.split(':')[0].lower()
            elif hasattr(host, 'environ'):
                # older calling convention: db_filter(dbs, httprequest)
                resolved_host = (host.environ.get('HTTP_HOST', '') or '').split(':')[0].lower()
        _logger.info(
            "SaaS resolver: db_filter called host_type=%s raw_host=%s resolved_host=%s dbs_count=%s",
            host_type,
            host,
            resolved_host,
            len(dbs) if dbs is not None else 'None',
        )
        if resolved_host:
            dbname = _get_database_from_mapping(resolved_host)
            if dbname:
                _logger.info("SaaS resolver: %s → '%s'", resolved_host, dbname)
                return [dbname]
            _logger.warning("SaaS resolver: no mapping for host=%s, fallback to original db_filter", resolved_host)
        else:
            _logger.warning("SaaS resolver: could not resolve host from input=%s, fallback to original db_filter", host)
        return original_db_filter(dbs, host)

    http_module.db_filter = patched_db_filter
    _logger.info("SaaS resolver: db_filter patched")