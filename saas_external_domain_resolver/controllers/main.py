from odoo import http
import time

class ResolverTestController(http.Controller):
    @http.route('/test-resolver', type='http', auth='public', methods=['GET'])
    def test_resolver(self):
        try:
            with open('/tmp/resolver_controller.txt', 'a') as f:
                f.write(f"Controller hit at {time.time()}\n")
        except Exception:
            pass
        return "Resolver module loaded - controller works!"