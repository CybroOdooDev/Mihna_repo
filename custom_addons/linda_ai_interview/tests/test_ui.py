from odoo.tests import HttpCase, tagged

from .common import LindaCommon

WAIT = """
const wait = (sel, text) => new Promise((resolve, reject) => {
    let n = 0;
    const timer = setInterval(() => {
        const el = document.querySelector(sel);
        if (el && (!text || el.textContent.includes(text))) { clearInterval(timer); resolve(el); }
        else if (++n > 150) { clearInterval(timer); reject(new Error("not found: " + sel + " " + (text || ""))); }
    }, 100);
});
"""


@tagged("post_install", "-at_install", "linda")
class TestUI(HttpCase, LindaCommon):
    """Smoke tests: the OWL apps compile, mount and render real data in Chrome (any JS error fails)."""

    def test_candidate_app_renders(self):
        session = self._invite()
        code = WAIT + """
            wait('.o_linda_app h2', "I'm Linda")
                .then(() => wait('.o_linda_notice_box', 'What we record'))
                .then(() => console.log('test successful'))
                .catch((e) => console.error(e.message));
        """
        self.browser_js(f"/linda/i/{session.access_token}", code, ready="", timeout=60)

    def test_candidate_app_coding_section_renders(self):
        session = self._invite()
        session._portal_consent(True)
        session._portal_start()
        session._portal_submit_section()
        code = WAIT + """
            wait('.o_linda_code textarea')
                .then(() => wait('.o_linda_problem h4', 'Second largest'))
                .then(() => wait('.o_linda_timer'))
                .then(() => console.log('test successful'))
                .catch((e) => console.error(e.message));
        """
        self.browser_js(f"/linda/i/{session.access_token}", code, ready="", timeout=60)

    def test_dashboards_render(self):
        campaign = self.env["ai.interview.campaign"].create({
            "name": "UI drive", "job_id": self.job.id, "template_id": self.template.id})
        campaign.action_start()
        campaign.applicant_ids = [(6, 0, self.applicant.ids)]
        campaign.action_invite_applicants()
        session = campaign.session_ids
        self._complete_interview(session)
        session._run_scoring()
        code = WAIT + """
            wait('.o_linda_dashboard .o_linda_kpis')
                .then(() => wait('.o_linda_table tbody tr', 'Anu Krishnan'))
                .then(() => wait('.o_linda_chart canvas'))
                .then(() => console.log('test successful'))
                .catch((e) => console.error(e.message));
        """
        self.browser_js(f"/odoo/action-linda_campaign_dashboard?active_id={campaign.id}", code, ready="",
                        login="admin", timeout=90)
        code = WAIT + """
            wait('.o_linda_evidence')
                .then(() => wait('.o_linda_dash_header h2', 'Anu Krishnan'))
                .then(() => wait('.nav-tabs .nav-link', 'Written English'))
                .then(() => console.log('test successful'))
                .catch((e) => console.error(e.message));
        """
        self.browser_js(f"/odoo/action-linda_candidate_dashboard?active_id={session.id}", code, ready="",
                        login="admin", timeout=90)

