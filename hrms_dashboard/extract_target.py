import json, re

try:
    with open("/home/cybrosys/Downloads/Open HRMS Dashboard(1).html", "r") as f:
        content = f.read()
    match = re.search(r'<script type="__bundler/template">(.*?)</script>', content, re.DOTALL)
    if match:
        template = match.group(1)
        # It's a JSON string containing the HTML
        html_content = json.loads(template)
        with open("extracted_target.html", "w") as out_f:
            out_f.write(html_content)
        print("Successfully extracted HTML to extracted_target.html")
    else:
        print("Could not find __bundler/template script tag.")
except Exception as e:
    print(f"Error: {e}")
