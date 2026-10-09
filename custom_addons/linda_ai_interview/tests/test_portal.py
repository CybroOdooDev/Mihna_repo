from odoo.tests import HttpCase, tagged

from ..services import speech
from .common import LindaCommon


@tagged("post_install", "-at_install", "linda")
class TestPortal(HttpCase, LindaCommon):

    def _api(self, token, route, **params):
        res = self.make_jsonrpc_request(f"/linda/api/{token}/{route}", params)
        self.assertTrue(res["ok"], res)
        return res["result"]

    def test_candidate_routes(self):
        session = self._invite()
        token = session.access_token
        page = self.url_open(f"/linda/i/{token}")
        self.assertEqual(page.status_code, 200)
        self.assertIn("linda_ai_interview.CandidateApp", page.text)
        bad = self.url_open("/linda/i/not-a-token")
        self.assertIn("not valid", bad.text)
        mobile = self.url_open(f"/linda/i/{token}", headers={"User-Agent": "Mozilla/5.0 (iPhone; Mobile)"})
        self.assertIn("laptop or desktop", mobile.text)

        state = self._api(token, "state", fresh_load=True)
        self.assertEqual(state["state"], "invited")
        self.assertIn("Linda", state["persona"])
        self.assertTrue(state["notice"]["html"])
        self._api(token, "consent", accept=True)
        started = self._api(token, "start")
        self.assertTrue(started["started"])
        items = started["state"]["items"]
        self.assertEqual(items[0]["section"], "written")
        self._api(token, "save", response_id=items[0]["id"], answer_text="Hello",
                  keystrokes=[[1, "i", 5, 0, "Hello"], [2, "p", 0, 0]])
        self.assertIn("paste", session.flag_ids.mapped("type"))
        self._api(token, "event", etype="tab_switch", detail="hidden")
        state = self._api(token, "submit_section")
        self.assertEqual(state["current_section"], "coding")
        item = state["items"][0]
        run = self._api(token, "run_code", response_id=item["id"], code="print(3)", language="python")
        self.assertTrue(run["results"])
        self._api(token, "submit_code", response_id=item["id"], code="print(3)", language="python")
        state = self._api(token, "submit_section")
        state = self._api(token, "submit_section")
        self.assertEqual(state["current_section"], "voice")
        voice_item = state["items"][0]
        tts = self.url_open(f"/linda/api/{token}/tts/{voice_item['id']}/-1")
        self.assertEqual(tts.status_code, 200)
        wav = speech.synthesize({"kind": "mock"}, "answer")[0]
        res = self.url_open(f"/linda/api/{token}/audio", data={"response_id": voice_item["id"], "index": "-1",
                                                             "silence_ms": "800"},
                            files={"audio": ("answer.wav", wav, "audio/wav")}).json()
        self.assertTrue(res["ok"], res)
        self.assertTrue(res["result"]["answered"])
        state = self._api(token, "submit_section")
        self.assertEqual(state["state"], "submitted")

        # Recordings are not reachable without a Recruitment login.
        att = session.response_ids.audio_attachment_ids[:1]
        resp = self.url_open(f"/linda/backend/audio/{att.id}", allow_redirects=False)
        self.assertNotEqual(resp.status_code, 200)
        recruiter = self.env["res.users"].create({
            "name": "Test Recruiter",
            "login": "test_recruiter_portal",
            "password": "password",
            "group_ids": [(6, 0, [self.env.ref("hr_recruitment.group_hr_recruitment_user").id])],
        })
        self.authenticate("test_recruiter_portal", "password")
        resp = self.url_open(f"/linda/backend/audio/{att.id}")
        self.assertEqual(resp.status_code, 200)
