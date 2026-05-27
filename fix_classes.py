import os

file_path = "/home/cybrosys/odoo19/custom_addons/subscription_management/views/subscription_templates.xml"

with open(file_path, "r") as f:
    content = f.read()

# Replace saas custom classes with standard bootstrap classes
replacements = {
    "portal-subscription-wrap": "",
    "saas-card-header": "card-header bg-white border-bottom",
    "saas-card": "shadow-sm",
    "saas-table": "",
    "saas-badge-success": "text-bg-success",
    "saas-badge-info": "text-bg-info",
    "saas-badge-warning": "text-bg-warning",
    "saas-badge-danger": "text-bg-danger",
    "saas-text-primary": "text-primary",
    "saas-text-muted": "text-muted",
    "saas-text-dark": "text-dark",
    "saas-forecast-card": "shadow-sm border",
    "saas-forecast-header": "bg-light border-bottom",
    "saas-btn-outline": "btn-outline-primary"
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open(file_path, "w") as f:
    f.write(content)

print("Successfully replaced custom classes in detail view.")
