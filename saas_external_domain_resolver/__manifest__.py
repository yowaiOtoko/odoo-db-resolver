{
    'name': 'SaaS External Domain Resolver',
    'version': '19.0.1.0.0',
    'summary': 'Resolve subdomain/domain to correct database from external mapping',
    'author': 'Invo Facturation',
    'website': 'https://invo-facturation.fr',
    'license': 'LGPL-3',
    'depends': ['base'],
    'installable': True,
    'auto_install': True,
    'post_load': 'post_load',
}