"""Tag existing AI call logs with their interview section and phase (token usage per section).

New calls are tagged when they are made; older ones are inferred from the task name and prompt.
"""


def migrate(cr, version):
    cr.execute("""
        UPDATE ai_interview_call_log
           SET section = CASE
                   WHEN task LIKE 'score\\_coding\\_%%' THEN 'coding'
                   WHEN task LIKE 'score\\_learning\\_%%' THEN 'learn'
                   WHEN task LIKE 'score\\_written\\_english\\_%%' THEN 'written'
                   WHEN task LIKE 'score\\_oral\\_english\\_%%' OR task LIKE 'score\\_attitude\\_%%' THEN 'voice'
                   WHEN task IN ('interviewer_turn', 'transcribe', 'synthesize') THEN 'voice'
                   WHEN task = 'code_followups' THEN 'coding'
                   WHEN task = 'ask_doc' THEN 'learn'
                   WHEN task = 'reference_answer' THEN 'written'
                   WHEN task = 'generate_questions' AND request LIKE '%%Voice interview%%' THEN 'voice'
                   WHEN task = 'generate_questions' THEN 'written'
                   ELSE 'general'
               END,
               phase = CASE
                   WHEN task LIKE 'score\\_%%' OR task IN ('reference_answer', 'written_spoken_gap')
                        OR role = 'stt_accurate' THEN 'scoring'
                   ELSE 'interview'
               END
         WHERE session_id IS NOT NULL AND section IS NULL
    """)
