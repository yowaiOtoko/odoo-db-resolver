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