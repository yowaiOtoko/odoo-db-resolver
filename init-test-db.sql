-- Test database initialization for SaaS External Domain Resolver

-- Create the tenant domain mapping table for testing
CREATE TABLE IF NOT EXISTS tenant_domain_mapping (
    domain VARCHAR(255) PRIMARY KEY,
    odoo_database VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_test_tenant_domain_mapping_domain ON tenant_domain_mapping(domain);
CREATE INDEX IF NOT EXISTS idx_test_tenant_domain_mapping_active ON tenant_domain_mapping(is_active);

-- Insert test data
INSERT INTO tenant_domain_mapping (domain, odoo_database, is_active) VALUES
('client1.test.com', 'client1_db', true),
('client2.test.com', 'client2_db', true),
('inactive.test.com', 'inactive_db', false),
('cache.test.com', 'cache_db', true),
('performance.test.com', 'performance_db', true)
ON CONFLICT (domain) DO NOTHING;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_test_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_test_tenant_domain_mapping_updated_at
    BEFORE UPDATE ON tenant_domain_mapping
    FOR EACH ROW EXECUTE FUNCTION update_test_updated_at_column();