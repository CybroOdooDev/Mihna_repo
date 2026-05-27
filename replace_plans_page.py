import sys
import re

file_path = '/home/cybrosys/odoo19/custom_addons/subscription_management/views/subscription_templates.xml'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Define the new template
new_template = """    <template id="subscription_plans_page" name="Subscription Plans">
        <t t-call="website.layout">
            <div id="wrap" class="oe_structure oe_empty" style="background-color: #020617;">
                <style>
                    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&amp;display=swap');
                    
                    .subscription-pricing-section {
                        font-family: 'Outfit', sans-serif !important;
                        background-color: #020617 !important; /* True slate black */
                        color: #f8fafc !important;
                        padding: 120px 0;
                        position: relative;
                        overflow: hidden;
                        min-height: 100vh;
                    }
                    
                    /* Dynamic glowing orbs */
                    .pricing-bg-glow {
                        position: absolute;
                        width: 800px;
                        height: 800px;
                        background: radial-gradient(circle, rgba(79, 70, 229, 0.15) 0%, rgba(2, 6, 23, 0) 70%);
                        top: -200px;
                        left: -300px;
                        border-radius: 50%;
                        pointer-events: none;
                        z-index: 1;
                        animation: float 20s ease-in-out infinite;
                    }
                    
                    .pricing-bg-glow-right {
                        position: absolute;
                        width: 800px;
                        height: 800px;
                        background: radial-gradient(circle, rgba(14, 165, 233, 0.1) 0%, rgba(2, 6, 23, 0) 70%);
                        bottom: -200px;
                        right: -300px;
                        border-radius: 50%;
                        pointer-events: none;
                        z-index: 1;
                        animation: float 25s ease-in-out infinite reverse;
                    }

                    @keyframes float {
                        0% { transform: translateY(0px) scale(1); }
                        50% { transform: translateY(-50px) scale(1.05); }
                        100% { transform: translateY(0px) scale(1); }
                    }
                    
                    .pricing-title-gradient {
                        background: linear-gradient(135deg, #f8fafc 0%, #94a3b8 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                        font-weight: 800;
                        font-size: 4rem;
                        letter-spacing: -2px;
                        line-height: 1.1;
                    }
                    
                    .pricing-subtitle {
                        color: #94a3b8;
                        font-size: 1.25rem;
                        max-width: 650px;
                        margin: 0 auto;
                        font-weight: 300;
                    }
                    
                    /* Glassmorphism Card */
                    .pricing-card-modern {
                        background: rgba(30, 41, 59, 0.4) !important;
                        backdrop-filter: blur(20px);
                        -webkit-backdrop-filter: blur(20px);
                        border: 1px solid rgba(255, 255, 255, 0.05) !important;
                        border-radius: 32px !important;
                        transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1) !important;
                        color: #f8fafc !important;
                        position: relative;
                        overflow: visible !important;
                        z-index: 2;
                        padding: 50px 40px;
                        box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.1) !important;
                    }
                    
                    .pricing-card-modern:hover {
                        transform: translateY(-15px) !important;
                        background: rgba(30, 41, 59, 0.6) !important;
                        border-color: rgba(99, 102, 241, 0.3) !important;
                        box-shadow: 0 30px 60px rgba(0, 0, 0, 0.5), 0 0 80px rgba(79, 70, 229, 0.15), inset 0 1px 0 rgba(255,255,255,0.2) !important;
                    }
                    
                    /* Featured card style */
                    .pricing-card-featured {
                        background: rgba(30, 41, 59, 0.6) !important;
                        border: 1px solid rgba(99, 102, 241, 0.5) !important;
                        box-shadow: 0 20px 50px rgba(79, 70, 229, 0.2), inset 0 1px 0 rgba(255,255,255,0.1) !important;
                        transform: scale(1.05);
                    }
                    
                    .pricing-card-featured:hover {
                        transform: translateY(-15px) scale(1.05) !important;
                        border-color: rgba(99, 102, 241, 0.8) !important;
                        box-shadow: 0 30px 60px rgba(0, 0, 0, 0.6), 0 0 100px rgba(79, 70, 229, 0.3), inset 0 1px 0 rgba(255,255,255,0.2) !important;
                    }
                    
                    .popular-badge {
                        position: absolute;
                        top: -18px;
                        left: 50%;
                        transform: translateX(-50%);
                        background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%);
                        color: #ffffff;
                        font-size: 0.85rem;
                        font-weight: 800;
                        text-transform: uppercase;
                        letter-spacing: 2px;
                        padding: 8px 24px;
                        border-radius: 9999px;
                        box-shadow: 0 10px 25px rgba(99, 102, 241, 0.5);
                        z-index: 10;
                    }
                    
                    .plan-name-pill {
                        background: rgba(15, 23, 42, 0.6);
                        border: 1px solid rgba(255, 255, 255, 0.1);
                        border-radius: 9999px;
                        font-size: 0.8rem;
                        font-weight: 700;
                        letter-spacing: 1px;
                        color: #94a3b8;
                        display: inline-block;
                        padding: 6px 16px;
                        margin-bottom: 24px;
                        text-transform: uppercase;
                    }
                    
                    .featured-name-pill {
                        background: rgba(99, 102, 241, 0.1);
                        border: 1px solid rgba(99, 102, 241, 0.3);
                        color: #a5b4fc;
                    }
                    
                    .plan-title {
                        font-size: 2rem;
                        font-weight: 800;
                        letter-spacing: -0.5px;
                        margin-bottom: 20px;
                        color: #f8fafc;
                    }
                    
                    .price-container {
                        margin-bottom: 35px;
                        display: flex;
                        align-items: baseline;
                        justify-content: center;
                    }
                    
                    .price-val {
                        font-size: 4rem;
                        font-weight: 800;
                        letter-spacing: -2px;
                        color: #f8fafc;
                        background: linear-gradient(135deg, #ffffff 0%, #cbd5e1 100%);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    }
                    
                    .price-term {
                        font-size: 1.1rem;
                        color: #64748b;
                        margin-left: 8px;
                        font-weight: 500;
                    }
                    
                    .divider-modern {
                        height: 1px;
                        background: linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0) 100%);
                        margin: 30px 0;
                    }
                    
                    .features-list {
                        margin-bottom: 40px;
                    }
                    
                    .feature-item-modern {
                        display: flex;
                        align-items: center;
                        margin-bottom: 18px;
                        font-size: 1rem;
                        color: #cbd5e1;
                        text-align: left;
                        font-weight: 400;
                    }
                    
                    .feature-icon-wrapper {
                        background: rgba(16, 185, 129, 0.15);
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 14px;
                        flex-shrink: 0;
                        border: 1px solid rgba(16, 185, 129, 0.2);
                    }
                    
                    .feature-icon-check {
                        color: #34d399;
                        font-size: 0.8rem;
                    }
                    
                    .feature-icon-gift-wrapper {
                        background: rgba(14, 165, 233, 0.15);
                        border-radius: 50%;
                        width: 24px;
                        height: 24px;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin-right: 14px;
                        flex-shrink: 0;
                        border: 1px solid rgba(14, 165, 233, 0.2);
                    }
                    
                    .feature-icon-gift {
                        color: #38bdf8;
                        font-size: 0.8rem;
                    }
                    
                    .cta-btn-modern {
                        background: rgba(255, 255, 255, 0.05) !important;
                        border: 1px solid rgba(255, 255, 255, 0.1) !important;
                        color: #f8fafc !important;
                        border-radius: 16px !important;
                        padding: 16px 28px !important;
                        font-weight: 700 !important;
                        font-size: 1.1rem !important;
                        transition: all 0.3s ease !important;
                        width: 100%;
                        backdrop-filter: blur(10px);
                    }
                    
                    .cta-btn-modern:hover {
                        background: rgba(255, 255, 255, 0.1) !important;
                        border-color: rgba(255, 255, 255, 0.2) !important;
                        transform: translateY(-2px) !important;
                        color: #ffffff !important;
                    }
                    
                    .cta-btn-featured {
                        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
                        color: #ffffff !important;
                        border: none !important;
                        box-shadow: 0 10px 25px rgba(99, 102, 241, 0.4) !important;
                        position: relative;
                        overflow: hidden;
                    }
                    
                    .cta-btn-featured::after {
                        content: '';
                        position: absolute;
                        top: 0;
                        left: -100%;
                        width: 50%;
                        height: 100%;
                        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
                        transform: skewX(-20deg);
                        animation: shine 3s infinite;
                    }
                    
                    @keyframes shine {
                        0% { left: -100%; }
                        20% { left: 200%; }
                        100% { left: 200%; }
                    }
                    
                    .cta-btn-featured:hover {
                        box-shadow: 0 15px 35px rgba(99, 102, 241, 0.6) !important;
                        transform: translateY(-3px) !important;
                    }
                    
                    @keyframes fadeInUp {
                        from { opacity: 0; transform: translateY(40px); }
                        to { opacity: 1; transform: translateY(0); }
                    }
                    
                    .animate-fade-in-up {
                        animation: fadeInUp 1s cubic-bezier(0.16, 1, 0.3, 1) both;
                    }
                </style>
                
                <section class="subscription-pricing-section">
                    <div class="pricing-bg-glow"/>
                    <div class="pricing-bg-glow-right"/>
                    
                    <div class="container position-relative" style="z-index: 5;">
                        <!-- Header Title Block -->
                        <div class="text-center mb-5 pb-4 animate-fade-in-up">
                            <span class="badge mb-3 py-2 px-3" style="background: rgba(99,102,241,0.1); color: #818cf8; border: 1px solid rgba(99,102,241,0.2); border-radius: 20px; font-weight: 600; letter-spacing: 1px;">SUBSCRIPTIONS</span>
                            <h1 class="pricing-title-gradient mb-4">Choose Your Perfect Plan</h1>
                            <p class="pricing-subtitle">Unlock robust scaling and premium workflows. Switch or cancel anytime.</p>
                        </div>
                        
                        <!-- Pricing Grid -->
                        <div class="row align-items-stretch justify-content-center">
                            <t t-foreach="plans" t-as="plan">
                                <t t-set="is_popular" t-value="plan.is_popular"/>
                                
                                <div class="col-lg-4 col-md-6 mb-5 d-flex animate-fade-in-up" t-attf-style="animation-delay: #{plan_index * 200}ms;">
                                    <div t-attf-class="card pricing-card-modern w-100 border-0 #{'pricing-card-featured' if is_popular else ''}">
                                        <div t-if="is_popular" class="popular-badge">Most Popular</div>
                                        
                                        <!-- Top Header info -->
                                        <div class="text-center">
                                            <span t-attf-class="plan-name-pill #{'featured-name-pill' if is_popular else ''}" t-esc="plan.code"/>
                                            <h3 class="plan-title" t-esc="plan.name"/>
                                        </div>
                                        
                                        <!-- Price -->
                                        <div class="price-container">
                                            <span class="price-val" t-field="plan.total_price" t-options="{'widget': 'monetary', 'display_currency': plan.currency_id}"/>
                                            <span class="price-term">/ <t t-esc="plan.billing_period"/></span>
                                        </div>
                                        
                                        <div class="divider-modern"/>
                                        
                                        <!-- Plan Features -->
                                        <div class="features-list flex-grow-1">
                                            <div t-if="plan.description" class="feature-item-modern">
                                                <div class="feature-icon-wrapper">
                                                    <i class="fa fa-check feature-icon-check"/>
                                                </div>
                                                <span t-esc="plan.description"/>
                                            </div>
                                            <!-- Product inclusions from pricing_ids -->
                                            <t t-foreach="plan.pricing_ids" t-as="pricing_line">
                                                <div class="feature-item-modern">
                                                    <div class="feature-icon-wrapper" style="background: rgba(99, 102, 241, 0.15); border-color: rgba(99, 102, 241, 0.2);">
                                                        <i class="fa fa-cube" style="font-size: 0.8rem; color: #818cf8;"/>
                                                    </div>
                                                    <span>Includes <strong class="text-white"><t t-esc="pricing_line.product_id.name"/></strong></span>
                                                </div>
                                            </t>
                                            <div class="feature-item-modern">
                                                <div class="feature-icon-wrapper">
                                                    <i class="fa fa-check feature-icon-check"/>
                                                </div>
                                                <span>Billed <strong class="text-white text-capitalize"><t t-esc="plan.billing_period"/></strong></span>
                                            </div>
                                            <div t-if="plan.trial_period_days > 0" class="feature-item-modern">
                                                <div class="feature-icon-gift-wrapper">
                                                    <i class="fa fa-gift feature-icon-gift"/>
                                                </div>
                                                <span style="color: #38bdf8;">Includes a <strong class="text-white"><t t-esc="plan.trial_period_days"/>-day</strong> free trial</span>
                                            </div>
                                        </div>
                                        
                                        <!-- Action CTA -->
                                        <a t-attf-href="/subscriptions/checkout/#{plan.id}" t-attf-class="btn cta-btn-modern #{'cta-btn-featured' if is_popular else ''} mt-auto text-center">Get Started</a>
                                    </div>
                                </div>
                            </t>
                            
                            <t t-if="not plans">
                                <div class="col-12 text-center py-5 animate-fade-in-up" style="color: #94a3b8;">
                                    <i class="fa fa-rocket fa-4x mb-4" style="color: #334155;"></i>
                                    <h3 class="text-white">Coming Soon</h3>
                                    <p class="lead">We are currently crafting our subscription plans.</p>
                                </div>
                            </t>
                        </div>
                    </div>
                </section>
            </div>
        </t>
    </template>"""

# Using regex to replace the entire <template id="subscription_plans_page">...</template>
pattern = re.compile(r'    <template id="subscription_plans_page".*?</template>', re.DOTALL)
new_content = pattern.sub(new_template, content)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully replaced subscription_plans_page!")
