import psycopg2
from psycopg2.extras import DictCursor
import logging
import os
import time
from odoo.http import request

_logger = logging.getLogger(__name__)

class DomainResolverMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        # Test write to confirm middleware is called
        try:
            with open('/tmp/resolver_middleware.txt', 'a') as f:
                f.write(f"Middleware hit at {time.time()}\n")
        except Exception:
            pass

        host = environ.get('HTTP_HOST', '').split(':')[0].lower()
        if host:
            dbname = self._get_database_from_mapping(host)
            if dbname:
                _logger.info("Middleware resolved domain: %s → '%s'", host, dbname)
                # Set the DB for the request
                request.session.db = dbname
            else:
                _logger.warning("Middleware: No mapping for domain: %s", host)

        return self.app(environ, start_response)

    def _get_database_from_mapping(self, host):
        env = os.environ
        config = {
            'host': env.get('SAAS_MAPPING_DB_HOST', 'postgres'),
            'port': int(env.get('SAAS_MAPPING_DB_PORT', '5432')),
            'dbname': env.get('SAAS_MAPPING_DB_NAME', 'app'),
            'user': env.get('SAAS_MAPPING_DB_USER', 'app'),
            'password': env.get('SAAS_MAPPING_DB_PASSWORD', ''),
        }
        if not config['password']:
            _logger.error("SAAS_MAPPING_DB_PASSWORD not set!")
            return None
        try:
            with psycopg2.connect(**config, connect_timeout=2, application_name='odoo-saas-resolver-middleware') as conn:
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
            _logger.error("Middleware domain mapping error for %s: %s", host, e)
            return None