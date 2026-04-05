"""
Tests for cache functionality and invalidation.
"""

import unittest
import time
from unittest.mock import Mock, patch

from odoo.tests import TransactionCase

from ..models.saas_domain_resolver import IrHttp, clear_saas_domain_cache


class TestCacheFunctionality(TransactionCase):
    """Test cases for cache functionality."""

    def setUp(self):
        super().setUp()
        # Clear any existing cache
        try:
            clear_saas_domain_cache()
        except Exception:
            pass  # Ignore if cache clearing fails during setup

    def tearDown(self):
        super().tearDown()
        # Clear cache after each test
        try:
            clear_saas_domain_cache()
        except Exception:
            pass  # Ignore if cache clearing fails during teardown

    @patch('psycopg2.connect')
    def test_cache_hit_same_domain(self, mock_connect):
        """Test that cache is used for repeated calls to same domain."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = {'odoo_database': 'cached_db'}
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()

        # First call - should query database
        result1 = resolver._get_database_from_mapping('cache.test.com')
        self.assertEqual(result1, 'cached_db')
        self.assertEqual(mock_connect.call_count, 1)

        # Second call - should use cache (no additional database call)
        result2 = resolver._get_database_from_mapping('cache.test.com')
        self.assertEqual(result2, 'cached_db')
        self.assertEqual(mock_connect.call_count, 1)  # Still only 1 call

        # Third call - should still use cache
        result3 = resolver._get_database_from_mapping('cache.test.com')
        self.assertEqual(result3, 'cached_db')
        self.assertEqual(mock_connect.call_count, 1)  # Still only 1 call

    @patch('psycopg2.connect')
    def test_cache_miss_different_domains(self, mock_connect):
        """Test that cache is domain-specific."""
        # Mock database connection and cursor
        call_count = 0
        def mock_fetchone():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {'odoo_database': 'domain1_db'}
            elif call_count == 2:
                return {'odoo_database': 'domain2_db'}
            else:
                return None

        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = mock_fetchone
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()

        # First domain
        result1 = resolver._get_database_from_mapping('domain1.test.com')
        self.assertEqual(result1, 'domain1_db')
        self.assertEqual(mock_connect.call_count, 1)

        # Second domain - should query database again
        result2 = resolver._get_database_from_mapping('domain2.test.com')
        self.assertEqual(result2, 'domain2_db')
        self.assertEqual(mock_connect.call_count, 2)

        # Repeat first domain - should use cache
        result3 = resolver._get_database_from_mapping('domain1.test.com')
        self.assertEqual(result3, 'domain1_db')
        self.assertEqual(mock_connect.call_count, 2)  # No additional call

    @patch('psycopg2.connect')
    def test_cache_invalidation(self, mock_connect):
        """Test cache invalidation functionality."""
        # Mock database connection and cursor
        call_count = 0
        def mock_fetchone():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {'odoo_database': 'before_clear_db'}
            elif call_count == 2:
                return {'odoo_database': 'after_clear_db'}
            else:
                return None

        mock_cursor = Mock()
        mock_cursor.fetchone.side_effect = mock_fetchone
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()

        # First call
        result1 = resolver._get_database_from_mapping('invalidate.test.com')
        self.assertEqual(result1, 'before_clear_db')
        self.assertEqual(mock_connect.call_count, 1)

        # Second call - should use cache
        result2 = resolver._get_database_from_mapping('invalidate.test.com')
        self.assertEqual(result2, 'before_clear_db')
        self.assertEqual(mock_connect.call_count, 1)

        # Clear cache
        clear_saas_domain_cache()

        # Third call - should query database again with new result
        result3 = resolver._get_database_from_mapping('invalidate.test.com')
        self.assertEqual(result3, 'after_clear_db')
        self.assertEqual(mock_connect.call_count, 2)

    @patch('psycopg2.connect')
    def test_cache_with_none_results(self, mock_connect):
        """Test caching of None results."""
        # Mock database connection and cursor
        mock_cursor = Mock()
        mock_cursor.fetchone.return_value = None  # No mapping found
        mock_connection = Mock()
        mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value.__enter__.return_value = mock_connection

        resolver = IrHttp()

        # First call - should query database
        result1 = resolver._get_database_from_mapping('notfound.test.com')
        self.assertIsNone(result1)
        self.assertEqual(mock_connect.call_count, 1)

        # Second call - should use cache (None result cached)
        result2 = resolver._get_database_from_mapping('notfound.test.com')
        self.assertIsNone(result2)
        self.assertEqual(mock_connect.call_count, 1)  # No additional call

    def test_cache_clear_function_success(self):
        """Test the clear_saas_domain_cache function success case."""
        with patch('odoo.http.root') as mock_root:
            mock_registry = Mock()
            mock_root.registry = mock_registry

            # Should not raise exception
            clear_saas_domain_cache()

            # Verify cache clear was called
            mock_registry.clear_cache.assert_called_once_with('saas_domain_mapping')

    def test_cache_clear_function_error_handling(self):
        """Test the clear_saas_domain_cache function error handling."""
        with patch('odoo.http.root') as mock_root:
            mock_registry = Mock()
            mock_registry.clear_cache.side_effect = Exception("Cache clear failed")
            mock_root.registry = mock_registry

            # Should not raise exception
            clear_saas_domain_cache()

            # Verify cache clear was attempted
            mock_registry.clear_cache.assert_called_once_with('saas_domain_mapping')

    def test_cache_key_isolation(self):
        """Test that cache keys are properly isolated."""
        # This test ensures that the cache decorator uses the correct key
        # We can't easily test the actual timeout without waiting,
        # but we can verify the cache behavior is consistent

        call_log = []

        @patch('psycopg2.connect')
        def mock_database_call(mock_connect):
            def side_effect(*args, **kwargs):
                call_log.append(f"call_{len(call_log) + 1}")
                mock_cursor = Mock()
                mock_cursor.fetchone.return_value = {'odoo_database': f'db_{len(call_log)}'}
                mock_connection = Mock()
                mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
                return mock_connection
            mock_connect.return_value.__enter__.return_value = side_effect()

        with mock_database_call():
            resolver = IrHttp()

            # Different domains should result in different cache entries
            domains = ['domain1.test.com', 'domain2.test.com', 'domain1.test.com', 'domain3.test.com']

            for domain in domains:
                resolver._get_database_from_mapping(domain)

            # Should have 3 unique database calls (domain1, domain2, domain3)
            # domain1 is called twice but should only result in one database call due to caching
            self.assertEqual(len(call_log), 3)
            self.assertEqual(call_log, ['call_1', 'call_2', 'call_3'])

    @patch('psycopg2.connect')
    def test_cache_performance(self, mock_connect):
        """Test that caching improves performance by reducing database calls."""
        import time

        # Mock with slight delay to simulate database call
        def slow_connect(*args, **kwargs):
            time.sleep(0.01)  # 10ms delay
            mock_cursor = Mock()
            mock_cursor.fetchone.return_value = {'odoo_database': 'performance_db'}
            mock_connection = Mock()
            mock_connection.cursor.return_value.__enter__.return_value = mock_cursor
            return mock_connection

        mock_connect.return_value.__enter__.return_value = slow_connect()

        resolver = IrHttp()

        start_time = time.time()

        # Make multiple calls to the same domain
        for _ in range(10):
            result = resolver._get_database_from_mapping('performance.test.com')
            self.assertEqual(result, 'performance_db')

        end_time = time.time()
        total_time = end_time - start_time

        # With caching, this should be much faster than 10 * 0.01 = 0.1 seconds
        # Allow some tolerance for test environment variance
        self.assertLess(total_time, 0.05, "Caching should significantly reduce total time")


if __name__ == '__main__':
    unittest.main()