from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Update xml id of roles which have"""
    if not version:
        return
    # Can not change form to list on existing database. So delete the form views before upgrading the module
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["ir.ui.view"].search([('arch_fs', 'ilike', 'frepple/'), ('type', '=', 'form')]).unlink()

