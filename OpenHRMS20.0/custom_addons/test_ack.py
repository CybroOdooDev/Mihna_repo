import odoo
import sys
odoo.tools.config.parse_config(['-c', '/home/cybrosys/odoo20/odoo20.conf', '-d', 'hrms_db1'])
registry = odoo.registry('hrms_db1')
with registry.cursor() as cr:
    env = odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})
    user = env['res.users'].search([('login', '=', 'demo')], limit=1)
    if not user:
        print("Demo user not found")
        sys.exit(1)
    print("Demo User:", user.name)
    env = odoo.api.Environment(cr, user.id, {})
    ann = env['hr.announcement'].browse(4)
    print("Announcement name:", ann.name)
    print("Has Acknowledged Before:", ann.has_acknowledged)
    try:
        ann.action_acknowledge()
        print("Action acknowledge success")
    except Exception as e:
        print("Error:", e)
    print("Has Acknowledged After:", ann.has_acknowledged)
    print("Employee ID:", user.employee_id.id if hasattr(user, 'employee_id') and user.employee_id else None)
    print("Acknowledged IDs:", ann.sudo().acknowledged_employee_ids.ids)
