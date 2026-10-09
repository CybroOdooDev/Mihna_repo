{
    "name": "Linda – AI Interview",
    "version": "20.0.1.0.0",
    "category": "Human Resources/Recruitment",
    "summary": "AI-led first-round interviews for fresher developers with evidence-backed scorecards",
    "description": """
Linda runs an AI-led first-round interview (written English, coding, learn-and-apply and a
turn-based voice interview), scores five dimensions against a rubric with quoted evidence,
detects likely AI assistance from several signals, and writes a scorecard on the applicant.
Recruiters and tech leads still make every hiring decision.
""",
    "author": "Cybrosys Technologies",
    "license": "LGPL-3",
    "depends": ["hr_recruitment", "mail", "website"],
    "external_dependencies": {"python": ["requests"]},
    "data": [
        "security/ir.access.csv",
        "data/config_data.xml",
        "data/cron_data.xml",
        "data/mail_template_data.xml",
        "data/criterion_data.xml",
        "data/question_data.xml",
        "data/template_data.xml",
        "views/provider_views.xml",
        "views/question_views.xml",
        "views/criterion_views.xml",
        "views/template_views.xml",
        "views/session_views.xml",
        "views/campaign_views.xml",
        "views/hr_applicant_views.xml",
        "views/res_config_settings_views.xml",
        "views/portal_templates.xml",
        "wizard/question_generate_views.xml",
        "report/scorecard_report.xml",
        "views/menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "linda_ai_interview/static/src/candidate/keylog.js",
            "linda_ai_interview/static/src/dashboard/**/*",
            "linda_ai_interview/static/src/scss/dashboard.scss",
        ],
        "web.assets_frontend": [
            "linda_ai_interview/static/src/candidate/**/*",
            "linda_ai_interview/static/src/scss/candidate.scss",
        ],
    },
    "application": True,
    "installable": True,
}
