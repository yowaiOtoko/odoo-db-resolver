-- Create the tenant domain mapping table
CREATE TABLE IF NOT EXISTS tenant_domain_mapping (
    domain VARCHAR(255) PRIMARY KEY,
    odoo_database VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for performance
CREATE INDEX IF NOT EXISTS idx_tenant_domain_mapping_domain ON tenant_domain_mapping(domain);
CREATE INDEX IF NOT EXISTS idx_tenant_domain_mapping_active ON tenant_domain_mapping(is_active);

-- Insert sample data for development/testing
INSERT INTO tenant_domain_mapping (domain, odoo_database, is_active) VALUES
('client1.localhost', 'client1_db', true),
('client2.localhost', 'client2_db', true),
('demo.localhost', 'demo_db', true)
ON CONFLICT (domain) DO NOTHING;

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
CREATE TRIGGER update_tenant_domain_mapping_updated_at
    BEFORE UPDATE ON tenant_domain_mapping
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();