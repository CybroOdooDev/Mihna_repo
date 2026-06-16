def migrate(cr, version):
    cr.execute("""
        UPDATE ir_rule 
        SET domain_force = %s
        WHERE name = 'Employee Multi Company Rule'
    """, ("['|',('company_id','=',False),('company_id','in', company_ids)]",))
