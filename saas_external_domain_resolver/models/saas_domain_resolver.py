import os
import psycopg2
from psycopg2.extras import DictCursor
import logging
import time
from odoo import models, tools, http

_logger = logging.getLogger('odoo.addons.saas_external_domain_resolver')

# Test module load
_logger.info("Module saas_external_domain_resolver loaded at %s", time.time())

class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def _dispatch(self):
        # Test: Write to file to confirm this method is called
        _logger.info("Resolver _dispatch hit at %s", time.time())

        start_time = time.perf_counter()
        host = self._get_clean_host()
        if host:
            dbname = self._get_database_from_mapping(host)
            duration = (time.perf_counter() - start_time) * 1000
            if dbname:
                _logger.debug("Domain resolved: %s → '%s' (%.2fms)", host, dbname, duration)
                http.request.session.db = dbname
                # Bypass selector and redirect to login if DB resolved
                if http.request.httprequest.path == '/web/database/selector':
                    return http.request.redirect('/web/login')
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
        """TEMP HARDCODE FOR DEBUG - return fixed DB for localhost"""
        if host == 'localhost':
            _logger.info("TEMP HARDCODE: Returning 'odoo_devcorp_solutions_sarl_209' for %s", host)
            return 'odoo_devcorp_solutions_sarl_209'
        _logger.info("TEMP: No hardcoded mapping for %s, returning None", host)
        return None

def clear_saas_domain_cache():
    """Call this from your provisioning system after updating mappings"""
    try:
        http.root.registry.clear_cache('saas_domain_mapping')
        _logger.info("SaaS domain mapping cache cleared")
    except Exception as e:
        _logger.error("Failed to clear cache: %s", e)

def post_init_hook(cr, registry):
    _logger.info("Post init hook run at %s", time.time())