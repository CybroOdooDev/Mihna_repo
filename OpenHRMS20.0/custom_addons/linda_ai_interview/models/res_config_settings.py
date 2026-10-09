from odoo import api, fields, models

PREFIX = "linda_ai_interview."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    linda_lang_python = fields.Boolean("Python", config_parameter=PREFIX + "lang_python", default=True)
    linda_lang_c = fields.Boolean("C", config_parameter=PREFIX + "lang_c", default=True)
    linda_lang_cpp = fields.Boolean("C++", config_parameter=PREFIX + "lang_cpp", default=True)
    linda_lang_javascript = fields.Boolean("JavaScript", config_parameter=PREFIX + "lang_javascript", default=True)
    linda_max_concurrent = fields.Integer("Simultaneous interviews", config_parameter=PREFIX + "max_concurrent",
                                          default=1, help="Extra candidates wait in a queue. 0 = no limit.")
    linda_auto_invite = fields.Boolean("Auto-invite on stage", config_parameter=PREFIX + "auto_invite")
    linda_tts_voice = fields.Char("TTS voice", config_parameter=PREFIX + "tts_voice", default="af_heart")
    linda_retention_audio_days = fields.Integer("Audio", config_parameter=PREFIX + "retention_audio_days", default=180)
    linda_retention_transcript_days = fields.Integer("Transcripts", config_parameter=PREFIX + "retention_transcript_days",
                                                     default=180)
    linda_retention_keystrokes_days = fields.Integer("Keystroke logs",
                                                     config_parameter=PREFIX + "retention_keystrokes_days", default=180)
    linda_retention_scores_days = fields.Integer("Scores", config_parameter=PREFIX + "retention_scores_days",
                                                 default=0, help="0 = keep scores and decision.")

    @api.model
    def _linda_enabled_languages(self):
        params = self.env["ir.config_parameter"].sudo()
        enabled = []
        for code in ("python", "c", "cpp", "javascript"):
            if params.get_bool(PREFIX + f"lang_{code}"):  # seeded "True" in data; unset = disabled
                enabled.append(code)
        return enabled
