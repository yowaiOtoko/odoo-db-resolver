"""
Integration tests for database mapping operations.
Requires a test database to be running.
"""

import unittest
import os
from unittest.mock import patch

from odoo.tests import TransactionCase

from ..models.saas_domain_resolver import IrHttp
from ..test_config import test_db_manager, get_test_env_vars


class TestDatabaseMapping(TransactionCase):
    """Integration tests for database operations."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Set up test environment variables
        cls.original_env = {}
        for key, value in get_test_env_vars().items():
            cls.original_env[key] = os.environ.get(key)
            os.environ[key] = value

        # Set up test database
        try:
            test_db_manager.setup_test_data()
        except Exception as e:
            cls.skip_test_db = True
            print(f"Skipping database tests: {e}")
        else:
            cls.skip_test_db = False

    @classmethod
    def tearDownClass(cls):
        # Restore original environment
        for key, value in cls.original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        # Clean up test database
        if not cls.skip_test_db:
            try:
                test_db_manager.cleanup_test_data()
            except Exception:
                pass  # Ignore cleanup errors

        super().tearDownClass()

    def setUp(self):
        super().setUp()
        if self.skip_test_db:
            self.skipTest("Test database not available")

    def test_database_connection_success(self):
        """Test successful database connection and query execution."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('client1.test.com')

        self.assertEqual(result, 'client1_db')

    def test_database_mapping_not_found(self):
        """Test database mapping for non-existent domain."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('nonexistent.test.com')

        self.assertIsNone(result)

    def test_database_mapping_inactive_domain(self):
        """Test database mapping for inactive domain."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('inactive.test.com')

        self.assertIsNone(result)

    def test_database_mapping_multiple_calls(self):
        """Test multiple database mapping calls."""
        resolver = IrHttp()

        # Test various domains
        test_cases = [
            ('client1.test.com', 'client1_db'),
            ('client2.test.com', 'client2_db'),
            ('inactive.test.com', None),
            ('unknown.test.com', None),
        ]

        for domain, expected_db in test_cases:
            with self.subTest(domain=domain):
                result = resolver._get_database_from_mapping(domain)
                self.assertEqual(result, expected_db)

    @patch.dict(os.environ, {'SAAS_MAPPING_DB_HOST': 'invalid-host'})
    def test_database_connection_failure(self):
        """Test database connection failure handling."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('client1.test.com')

        self.assertIsNone(result)

    @patch.dict(os.environ, {'SAAS_MAPPING_DB_PORT': '9999'})  # Invalid port
    def test_database_connection_timeout(self):
        """Test database connection timeout handling."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('client1.test.com')

        self.assertIsNone(result)

    @patch.dict(os.environ, {'SAAS_MAPPING_DB_USER': 'invalid_user'})
    def test_database_authentication_failure(self):
        """Test database authentication failure handling."""
        resolver = IrHttp()
        result = resolver._get_database_from_mapping('client1.test.com')

        self.assertIsNone(result)

    def test_environment_variable_defaults(self):
        """Test environment variable defaults when not set."""
        # Temporarily clear environment variables
        env_vars_to_clear = [
            'SAAS_MAPPING_DB_HOST',
            'SAAS_MAPPING_DB_PORT',
            'SAAS_MAPPING_DB_NAME',
            'SAAS_MAPPING_DB_USER',
        ]

        cleared_vars = {}
        for var in env_vars_to_clear:
            cleared_vars[var] = os.environ.pop(var, None)

        try:
            # Test with minimal environment
            os.environ['SAAS_MAPPING_DB_PASSWORD'] = 'test_password'
            resolver = IrHttp()

            # This should fail because we're not using the test database
            # but it should use the default values
            result = resolver._get_database_from_mapping('test.com')
            self.assertIsNone(result)  # Should fail due to wrong defaults

        finally:
            # Restore environment variables
            for var, value in cleared_vars.items():
                if value is not None:
                    os.environ[var] = value

    def test_database_query_sql_injection_protection(self):
        """Test that database queries are protected against SQL injection."""
        resolver = IrHttp()

        # Test with potentially malicious domain names
        malicious_domains = [
            "'; DROP TABLE tenant_domain_mapping; --",
            "' OR '1'='1",
            "test.com'; SELECT * FROM users; --",
        ]

        for domain in malicious_domains:
            with self.subTest(domain=domain):
                # This should not cause any SQL injection or errors
                # The query uses parameterized statements, so it should be safe
                result = resolver._get_database_from_mapping(domain)
                # Result should be None since these domains don't exist
                self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()