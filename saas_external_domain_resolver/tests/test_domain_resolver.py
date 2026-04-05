"""
Unit tests for SaaS External Domain Resolver functionality.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import os
import logging
from io import StringIO

from odoo import http
from odoo.tests import TransactionCase

from ..models.saas_domain_resolver import IrHttp, clear_saas_domain_cache


class TestDomainResolver(TransactionCase):
    """Test cases for domain resolver functionality."""

    def setUp(self):
        super().setUp()
        # Capture logging output
        self.log_capture = StringIO()
        self.log_handler = logging.StreamHandler(self.log_capture)
        self.log_handler.setLevel(logging.DEBUG)
        logger = logging.getLogger('odoo.addons.saas_external_domain_resolver.models.saas_domain_resolver')
        logger.addHandler(self.log_handler)
        logger.setLevel(logging.DEBUG)

    def tearDown(self):
        super().tearDown()
        # Clean up logging
        logger = logging.getLogger('odoo.addons.saas_external_domain_resolver.models.saas_domain_resolver')
        logger.removeHandler(self.log_handler)

    def test_get_clean_host_with_port(self):
        """Test host extraction with port number."""
        # Create a mock HTTP request
        mock_request = Mock()
        mock_request.httprequest.host = 'example.com:8069'

        with patch('odoo.http.request', mock_request):
            resolver = IrHttp()
            result = resolver._get_clean_host()
            self.assertEqual(result, 'example.com')

    def test_get_clean_host_uppercase(self):
        """Test host extraction with uppercase conversion."""
        mock_request = Mock()
        mock_request.httprequest.host = 'EXAMPLE.COM'

        with patch('odoo.http.request', mock_request):
            resolver = IrHttp()
            result = resolver._get_clean_host()
            self.assertEqual(result, 'example.com')

    def test_get_clean_host_no_port(self):
        """Test host extraction without port."""
        mock_request = Mock()
        mock_request.httprequest.host = 'example.com'

        with patch('odoo.http.request', mock_request):
            resolver = IrHttp()
            result = resolver._get_clean_host()
            self.assertEqual(result, 'example.com')

    def test_get_clean_host_missing_header(self):
        """Test error handling when Host header is missing."""
        mock_request = Mock()
        mock_request.httprequest.host = None

        with patch('odoo.http.request', mock_request):
            resolver = IrHttp()
            result = resolver._get_clean_host()
            self.assertIsNone(result)

            # Check that warning was logged
            log_output = self.log_capture.getvalue()
            self.assertIn("Failed to read Host header", log_output)

    def test_get_clean_host_exception(self):
        """Test error handling when request object is malformed."""
        mock_request = Mock()
        mock_request.httprequest = None  # This will cause an exception

        with patch('odoo.http.request', mock_request):
            resolver = IrHttp()
            result = resolver._get_clean_host()
            self.assertIsNone(result)

            # Check that warning was logged
            log_output = self.log_capture.getvalue()
            self.assertIn("Failed to read Host header", log_output)

    @patch.dict(os.environ, {
        'SAAS_MAPPING_DB_HOST': 'test-host',
        'SAAS_MAPPING_DB_PORT': '5433',
        'SAAS_MAPPING_DB_NAME': 'test-db',
        'SAAS_MAPPING_DB_USER': 'test-user',
        'SAAS_MAPPING_DB_PASSWORD': 'test-password',
    })
    @patch('psycopg2.connect')
    def test_get_database_from_mapping_success(self, mock_connect):
        """Test successful database mapping lookup."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'odoo_database': 'client1_db'}
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()
        result = resolver._get_database_from_mapping('client1.test.com')

        self.assertEqual(result, 'client1_db')
        mock_cursor.execute.assert_called_once()
        args, kwargs = mock_cursor.execute.call_args
        self.assertIn('client1.test.com', args[1])

    @patch.dict(os.environ, {
        'SAAS_MAPPING_DB_PASSWORD': 'test-password',
    })
    @patch('psycopg2.connect')
    def test_get_database_from_mapping_no_result(self, mock_connect):
        """Test database mapping lookup with no results."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()
        result = resolver._get_database_from_mapping('unknown.test.com')

        self.assertIsNone(result)
        mock_cursor.execute.assert_called_once()

    @patch.dict(os.environ, {
        'SAAS_MAPPING_DB_PASSWORD': '',
    })
    def test_get_database_from_mapping_no_password(self):
        """Test database mapping lookup with missing password."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('test.com')

        self.assertIsNone(result)
        # Check that error was logged
        log_output = self.log_capture.getvalue()
        self.assertIn("SAAS_MAPPING_DB_PASSWORD environment variable is not set", log_output)

    @patch.dict(os.environ, {
        'SAAS_MAPPING_DB_PASSWORD': 'test-password',
    })
    @patch('psycopg2.connect')
    def test_get_database_from_mapping_connection_error(self, mock_connect):
        """Test database mapping lookup with connection error."""
        mock_connect.side_effect = Exception("Connection failed")

        resolver = IrHttp()
        result = resolver._get_database_from_mapping('test.com')

        self.assertIsNone(result)
        # Check that error was logged
        log_output = self.log_capture.getvalue()
        self.assertIn("Domain mapping error for test.com", log_output)

    @patch('odoo.http.request')
    def test_dispatch_with_valid_domain(self, mock_request):
        """Test dispatch method with valid domain mapping."""
        # Mock request components
        mock_request.httprequest.host = 'client1.test.com'
        mock_request.session.db = None
        mock_request.env.cr.dbname = 'default_db'

        # Mock the resolver methods
        resolver = IrHttp()

        with patch.object(resolver, '_get_clean_host', return_value='client1.test.com'), \
             patch.object(resolver, '_get_database_from_mapping', return_value='client1_db'), \
             patch('odoo.models.AbstractModel._dispatch') as mock_super_dispatch:

            result = resolver._dispatch()

            # Verify database assignment
            self.assertEqual(mock_request.session.db, 'client1_db')
            self.assertEqual(mock_request.env.cr.dbname, 'client1_db')

            # Verify logging
            log_output = self.log_capture.getvalue()
            self.assertIn("Domain resolved: client1.test.com → 'client1_db'", log_output)

            # Verify super dispatch was called
            mock_super_dispatch.assert_called_once()

    @patch('odoo.http.request')
    def test_dispatch_with_unknown_domain(self, mock_request):
        """Test dispatch method with unknown domain."""
        mock_request.httprequest.host = 'unknown.test.com'
        mock_request.session.db = None
        mock_request.env.cr.dbname = 'default_db'

        resolver = IrHttp()

        with patch.object(resolver, '_get_clean_host', return_value='unknown.test.com'), \
             patch.object(resolver, '_get_database_from_mapping', return_value=None), \
             patch('odoo.models.AbstractModel._dispatch') as mock_super_dispatch:

            result = resolver._dispatch()

            # Verify database was not changed
            self.assertIsNone(mock_request.session.db)
            self.assertEqual(mock_request.env.cr.dbname, 'default_db')

            # Verify warning was logged
            log_output = self.log_capture.getvalue()
            self.assertIn("No mapping found for domain: unknown.test.com", log_output)

            # Verify super dispatch was called
            mock_super_dispatch.assert_called_once()

    @patch('odoo.http.request')
    def test_dispatch_with_no_host(self, mock_request):
        """Test dispatch method when no host is available."""
        mock_request.httprequest.host = None

        resolver = IrHttp()

        with patch.object(resolver, '_get_clean_host', return_value=None), \
             patch('odoo.models.AbstractModel._dispatch') as mock_super_dispatch:

            result = resolver._dispatch()

            # Verify super dispatch was called without any database changes
            mock_super_dispatch.assert_called_once()

    def test_clear_saas_domain_cache_success(self):
        """Test successful cache clearing."""
        with patch('odoo.http.root') as mock_root:
            mock_registry = Mock()
            mock_root.registry = mock_registry

            clear_saas_domain_cache()

            mock_registry.clear_cache.assert_called_once_with('saas_domain_mapping')

            # Check that success was logged
            log_output = self.log_capture.getvalue()
            self.assertIn("SaaS domain mapping cache cleared", log_output)

    def test_clear_saas_domain_cache_error(self):
        """Test cache clearing with error."""
        with patch('odoo.http.root') as mock_root:
            mock_registry = Mock()
            mock_registry.clear_cache.side_effect = Exception("Cache clear failed")
            mock_root.registry = mock_registry

            clear_saas_domain_cache()

            # Check that error was logged
            log_output = self.log_capture.getvalue()
            self.assertIn("Failed to clear cache", log_output)


if __name__ == '__main__':
    unittest.main()