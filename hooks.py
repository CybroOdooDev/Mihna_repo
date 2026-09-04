# -*- coding: utf-8 -*-
"""post_init_hook - runs once, only on a fresh install of this module (not on later upgrades),
right after data/res_company_data.xml has created the 'UAE Company (Aigentrix)' demo company.

Odoo only makes a newly-created company selectable for users who already have it in their
'Allowed Companies' - a brand-new company otherwise sits invisible in the company switcher. This
grants access to whichever user is installing the module and to the standard Administrator, so
the company is immediately usable without extra manual setup.
"""
from odoo import Command


def post_init_hook(env):
    company = env.ref('l10n_ae_aigentrix.demo_company_ae', raise_if_not_found=False)
    if not company:
        return
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    users = (env.user | admin) if admin else env.user
    for user in users:
        if company not in user.company_ids:
            user.company_ids = [Command.link(company.id)]
