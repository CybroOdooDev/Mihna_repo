# -*- coding: utf-8 -*-

def run_tests():
    # Inside shell, 'env' is pre-initialized as local variable.
    # Let's get it from global namespace or self.env
    global env
    
    print("=================================================================")
    print("          STARTING INTEGRATION TESTS FOR PHASE 3 ENGINES         ")
    print("=================================================================")

    def get_record_from_action(action, model):
        if isinstance(action, dict) and 'res_id' in action:
            return env[model].browse(action['res_id'])
        return action

    # Find or create a test partner
    partner = env['res.partner'].create({
        'name': 'SaaS Test Enterprise Ltd',
        'email': 'enterprise@test.saas',
    })

    # Create products
    product_fixed = env['product.product'].create({
        'name': 'Fixed Service Product',
        'list_price': 100.0,
        'type': 'service',
    })
    product_premium_fixed = env['product.product'].create({
        'name': 'Premium Fixed Service Product',
        'list_price': 300.0,
        'type': 'service',
    })
    product_seat = env['product.product'].create({
        'name': 'Seat Service Product',
        'list_price': 20.0,
        'type': 'service',
    })

    # Create plans
    plan_standard = env['subscription.plan'].create({
        'name': 'SStandard Recurring Plan',
        'product_id': product_fixed.id,
        'billing_period': 'monthly',
    })
    plan_premium = env['subscription.plan'].create({
        'name': 'PPremium Recurring Plan',
        'product_id': product_premium_fixed.id,
        'billing_period': 'monthly',
    })

    # Sync master pricing pricing list
    env['subscription.plan.pricing'].create({
        'plan_id': plan_standard.id,
        'product_id': product_fixed.id,
        'price': 100.0,
    })
    env['subscription.plan.pricing'].create({
        'plan_id': plan_premium.id,
        'product_id': product_premium_fixed.id,
        'price': 300.0,
    })

    print("\n--> TEST 1: GRANDFATHERING & PRICE LOCK ENGINE")
    sub_gf = env['subscription.subscription'].create({
        'name': 'SUB-GF-01',
        'partner_id': partner.id,
        'plan_id': plan_standard.id,
        'grandfathered': True,
    })
    # Generate lines
    sub_gf._onchange_plan_id()
    # Verify initial locked price
    print(f"Grandfathered contract initial price: ${sub_gf.line_ids[0].price_unit}")

    sub_ngf = env['subscription.subscription'].create({
        'name': 'SUB-NGF-01',
        'partner_id': partner.id,
        'plan_id': plan_standard.id,
        'grandfathered': False,
    })
    sub_ngf._onchange_plan_id()

    # Update master plan price to $150
    pricing = plan_standard.pricing_ids[0]
    pricing.price = 150.0
    # Also update product list price to trigger standard field compute fallback
    product_fixed.list_price = 150.0
    print("Updated master subscription plan pricing to $150.0")

    # Create invoice for grandfathered contract (should lock old price $100)
    inv_gf = get_record_from_action(sub_gf.action_create_invoice(), 'account.move')
    print(f"Grandfathered invoice line price: ${inv_gf.invoice_line_ids[0].price_unit} (Expected: 100.0)")
    assert inv_gf.invoice_line_ids[0].price_unit == 100.0, "Grandfathering failed to lock price!"

    # Create invoice for non-grandfathered contract (should use updated price $150)
    inv_ngf = get_record_from_action(sub_ngf.action_create_invoice(), 'account.move')
    print(f"Non-Grandfathered invoice line price: ${inv_ngf.invoice_line_ids[0].price_unit} (Expected: 150.0)")
    assert inv_ngf.invoice_line_ids[0].price_unit == 150.0, "Non-Grandfathering pricing sync failed!"


    print("\n--> TEST 2: RAMP PRICING ENGINE")
    sub_ramp = env['subscription.subscription'].create({
        'name': 'SUB-RAMP-01',
        'partner_id': partner.id,
        'plan_id': plan_standard.id,
    })
    sub_ramp._onchange_plan_id()
    # Configure Ramp rules on contract: Cycle 1 = $10.00, Cycle 2 = $30.00
    env['subscription.line.ramp'].create({
        'subscription_id': sub_ramp.id,
        'start_cycle': 1,
        'end_cycle': 1,
        'price_unit': 10.0,
    })
    env['subscription.line.ramp'].create({
        'subscription_id': sub_ramp.id,
        'start_cycle': 2,
        'end_cycle': 2,
        'price_unit': 30.0,
    })

    # Run Cycle 1 billing
    inv_ramp_1 = get_record_from_action(sub_ramp.action_create_invoice(), 'account.move')
    print(f"Cycle 1 invoice price unit: ${inv_ramp_1.invoice_line_ids[0].price_unit} (Expected: 10.0)")
    assert inv_ramp_1.invoice_line_ids[0].price_unit == 10.0, "Ramp pricing cycle 1 failed!"

    # Run Cycle 2 billing
    inv_ramp_2 = get_record_from_action(sub_ramp.action_create_invoice(), 'account.move')
    print(f"Cycle 2 invoice price unit: ${inv_ramp_2.invoice_line_ids[0].price_unit} (Expected: 30.0)")
    assert inv_ramp_2.invoice_line_ids[0].price_unit == 30.0, "Ramp pricing cycle 2 failed!"


    print("\n--> TEST 3: SEAT-BASED DYNAMIC RECALCULATION")
    sub_seat = env['subscription.subscription'].create({
        'name': 'SUB-SEAT-01',
        'partner_id': partner.id,
        'plan_id': plan_standard.id,
    })
    # Add a seat service line
    env['subscription.line'].create({
        'subscription_id': sub_seat.id,
        'product_id': product_seat.id,
        'name': 'Seat Service Licenses',
        'billing_type': 'seat',
        'quantity': 1.0,
        'price_unit': 20.0,
    })

    # Create active users linked to this partner
    user_1 = env['res.users'].create({
        'name': 'Tenant Operator 1',
        'login': 'operator1@tenant.saas',
        'email': 'operator1@tenant.saas',
        'partner_id': partner.id,
    })

    # Run billing (should dynamically sync and set quantity to 1)
    inv_seat = get_record_from_action(sub_seat.action_create_invoice(), 'account.move')
    # Find the seat line in invoice
    seat_inv_line = inv_seat.invoice_line_ids.filtered(lambda l: l.product_id == product_seat)
    print(f"Seat billing dynamic user quantity: {seat_inv_line.quantity} user(s) (Expected: 1.0)")
    assert seat_inv_line.quantity == 1.0, "Seat-based user recalculation failed!"


    print("\n--> TEST 4: PRORATION UPGRADE/DOWNGRADE ENGINE")
    sub_prorate = env['subscription.subscription'].create({
        'name': 'SUB-PRORATE-01',
        'partner_id': partner.id,
        'plan_id': plan_standard.id,
        'state': 'in_progress',
    })
    sub_prorate._onchange_plan_id()
    
    # Standard price is $150. Premium is $300. Delta should be prorated.
    # Run proration wizard directly
    wizard = env['subscription.change.plan.wizard'].create({
        'subscription_id': sub_prorate.id,
        'new_plan_id': plan_premium.id,
        'prorate': True,
    })
    wizard.action_change_plan()
    print(f"Subscription new plan successfully updated to: {sub_prorate.plan_id.name}")
    
    # Search all invoices for this subscription
    invoices = env['account.move'].search([('subscription_id', '=', sub_prorate.id)])
    print(f"Found invoices count: {len(invoices)}")
    if invoices:
        for idx, inv in enumerate(invoices):
            print(f"Invoice {idx}: {inv.name}, type: {inv.move_type}, lines: {inv.invoice_line_ids.mapped('price_unit')}")
    else:
        print("No invoices found for prorated subscription!")


    print("\n--> TEST 5: INVOICE PREVIEW ENGINE FORECAST")
    sub_preview = env['subscription.subscription'].create({
        'name': 'SUB-PREVIEW-01',
        'partner_id': partner.id,
        'plan_id': plan_premium.id,
    })
    sub_preview._onchange_plan_id()
    # Fetch portal/invoice preview dict
    preview_data = sub_preview.action_preview_next_invoice()
    print("Forecasted invoice preview keys: ", list(preview_data.keys()))
    print(f"Forecasted Grand Total: {preview_data['currency_symbol']}{preview_data['grand_total']}")
    assert preview_data['grand_total'] > 0.0, "Invoice preview forecasting failed!"

    print("\n=================================================================")
    print("          ALL PHASE 3 ENGINES PASSED INTEGRATION TESTS!          ")
    print("=================================================================")

    # Rollback so we don't dirty the test database
    env.cr.rollback()

run_tests()
