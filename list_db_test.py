import sys
sys.path.append('/home/cybrosys/odoo19')
import odoo
odoo.tools.config.parse_config(['-c', '/home/cybrosys/odoo19/odoo19.conf'])
from odoo.service import db
try:
    print("Odoo DBs:", db.list_dbs(True))
except Exception as e:
    print("Error listing DBs:", e)
