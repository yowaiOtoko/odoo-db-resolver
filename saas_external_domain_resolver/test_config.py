"""
Test configuration utilities for SaaS External Domain Resolver tests.
"""

import os
import psycopg2
from psycopg2.extras import DictCursor


class TestDatabaseManager:
    """Manages test database connections and setup for tests."""

    def __init__(self):
        self.test_config = {
            'host': os.environ.get('TEST_DB_HOST', 'test-postgres'),
            'port': int(os.environ.get('TEST_DB_PORT', '5433')),
            'dbname': os.environ.get('TEST_DB_NAME', 'test_app'),
            'user': os.environ.get('TEST_DB_USER', 'test_app'),
            'password': os.environ.get('TEST_DB_PASSWORD', 'test_password'),
        }

    def get_connection(self):
        """Get a test database connection."""
        return psycopg2.connect(**self.test_config, connect_timeout=5)

    def setup_test_data(self):
        """Set up test data in the database."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Create test table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tenant_domain_mapping (
                        domain VARCHAR(255) PRIMARY KEY,
                        odoo_database VARCHAR(255) NOT NULL,
                        is_active BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                # Insert test data
                test_data = [
                    ('client1.test.com', 'client1_db', True),
                    ('client2.test.com', 'client2_db', True),
                    ('inactive.test.com', 'inactive_db', False),
                ]

                cur.executemany("""
                    INSERT INTO tenant_domain_mapping (domain, odoo_database, is_active)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (domain) DO UPDATE SET
                        odoo_database = EXCLUDED.odoo_database,
                        is_active = EXCLUDED.is_active;
                """, test_data)

            conn.commit()

    def cleanup_test_data(self):
        """Clean up test data."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DROP TABLE IF EXISTS tenant_domain_mapping;")
            conn.commit()


# Global test database manager instance
test_db_manager = TestDatabaseManager()


def get_test_env_vars():
    """Get environment variables for testing."""
    return {
        'SAAS_MAPPING_DB_HOST': 'test-postgres',
        'SAAS_MAPPING_DB_PORT': '5433',
        'SAAS_MAPPING_DB_NAME': 'test_app',
        'SAAS_MAPPING_DB_USER': 'test_app',
        'SAAS_MAPPING_DB_PASSWORD': 'test_password',
    }