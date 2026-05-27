import os

file_path = "/home/cybrosys/odoo19/custom_addons/subscription_management/views/subscription_templates.xml"

with open(file_path, "r") as f:
    content = f.read()

# Replace the promo section
old_promo = """                                        <!-- Step 3: Payment Details -->
                                        <h4 class="font-weight-bold mb-4 mt-5 text-white"><span class="saas-step-badge">3</span> Promo &amp; Payment</h4>
                                        <div class="p-4 mb-5" style="background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255,255,255,0.05); border-radius: 16px;">
                                            <!-- Promo Code / Coupon Section -->
                                            <div class="mb-2">
                                                <label for="coupon_code" class="form-label checkout-form-label">Promo / Coupon Code</label>
                                                <div class="input-group">
                                                    <input type="text" class="form-control checkout-form-input" id="coupon_code" name="coupon_code" placeholder="e.g. SAVE20" t-att-value="kw.get('coupon_code') if kw else ''" style="border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: none;"/>
                                                    <button class="btn font-weight-bold px-4" type="button" id="btn_apply_coupon" style="border-top-left-radius: 0; border-bottom-left-radius: 0; background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(99, 102, 241, 0.5); color: #818cf8; font-size: 0.95rem; transition: all 0.2s;">Apply</button>
                                                </div>
                                                <div id="coupon_msg" class="mt-2 small" style="display: none;"/>
                                            </div>
                                        </div>
                                
                                        <!-- Complete Button -->
                                        <button type="submit" class="btn btn-pay-modern mt-2">
                                            <span>Continue to Payment <i class="fa fa-arrow-right ms-2"></i></span>
                                        </button>
                                        
                                        <p class="text-center small mt-4 mb-0" style="color: #64748b;">
                                            <i class="fa fa-lock me-1"></i> Secure checkout. By continuing, you agree to our Terms of Service. Future renewals occur automatically.
                                        </p>
                                    </form>
                                </div>
                            </div>"""

new_promo = """                                            <h4 class="font-weight-bold mb-4 mt-5 border-bottom pb-2">3. Promo Code</h4>
                                            <div class="mb-5 bg-light p-3 rounded border">
                                                <label for="coupon_code" class="form-label font-weight-bold">Do you have a promo code?</label>
                                                <div class="input-group">
                                                    <input type="text" class="form-control" id="coupon_code" name="coupon_code" placeholder="Enter code here" t-att-value="kw.get('coupon_code') if kw else ''"/>
                                                    <button class="btn btn-outline-primary" type="button" id="btn_apply_coupon">Apply</button>
                                                </div>
                                                <div id="coupon_msg" class="mt-2 small" style="display: none;"/>
                                            </div>
                                            
                                            <button type="submit" class="btn btn-primary btn-lg w-100 py-3 font-weight-bold">
                                                Continue to Payment <i class="fa fa-arrow-right ms-2"></i>
                                            </button>
                                            
                                            <p class="text-center text-muted small mt-3">
                                                <i class="fa fa-lock me-1"></i> Secure checkout. By continuing, you agree to our Terms of Service.
                                            </p>
                                        </form>
                                    </div>
                                </div>
                            </div>"""

if old_promo in content:
    content = content.replace(old_promo, new_promo)
    with open(file_path, "w") as f:
        f.write(content)
    print("Successfully replaced.")
else:
    print("Could not find the target string.")
    
