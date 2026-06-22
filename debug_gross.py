import xmlrpc.client

try:
    db='odoo'
    user='admin'
    pwd='1'
    common = xmlrpc.client.ServerProxy('http://localhost:8019/xmlrpc/2/common')
    uid = common.authenticate(db, user, pwd, {})
    models = xmlrpc.client.ServerProxy('http://localhost:8019/xmlrpc/2/object')
    
    # get slip 48
    payslips = models.execute_kw(db, uid, pwd, 'hr.payslip', 'search_read', [[['employee_id.name', 'ilike', 'Ronnie Hart']]], {'fields': ['id', 'name'], 'limit': 1})
    
    if payslips:
        slip_id = payslips[0]['id']
        lines = models.execute_kw(db, uid, pwd, 'hr.payslip.line', 'search_read', [[['slip_id', '=', slip_id]]], {'fields': ['name', 'code', 'category_id', 'total']})
        with open('/home/cybrosys/odoo19/OpenHRMS-19.0/hr_payroll_community/debug_output.txt', 'w') as f:
            for l in lines:
                f.write(str(l) + '\n')
except Exception as e:
    with open('/home/cybrosys/odoo19/OpenHRMS-19.0/hr_payroll_community/debug_output.txt', 'w') as f:
        f.write(str(e))
