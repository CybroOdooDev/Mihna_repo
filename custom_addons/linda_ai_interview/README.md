# Linda – AI Interview (Odoo 19 Community)

Linda runs an AI-led first-round interview for fresher developers and writes an evidence-backed
scorecard on the applicant. Recruiters and tech leads still make every hiring decision.

Built from *AI Interview Tool — FRD* (Phase 1 scope).

## Install

```bash
pip install anthropic          # only needed for the Anthropic provider
odoo-bin -d <db> -i linda_ai_interview --addons-path=...,/path/to/ai_interview_tool
```

Depends on `hr_recruitment`, `mail`, `website`.

## Configure (Recruitment → Configuration → AI Interview (Linda))

1. **AI & speech providers** – one record per role. Defaults:
   | Role | Default | Notes |
   |---|---|---|
   | LLM – interviewer | Anthropic `claude-haiku-4-5` | low latency |
   | LLM – scorer | Anthropic `claude-sonnet-5-5` | runs twice per dimension, after submission |
   | LLM – generator | Anthropic `claude-sonnet-5-5` | question pool + reference AI answers (add up to 3 generator records to compare several models) |
   | STT fast / accurate | mock → Whisper | OpenAI-compatible `/v1/audio/transcriptions` |
   | TTS | mock → Kokoro | OpenAI-compatible `/v1/audio/speech` |
   | Sandbox | mock → Judge0 | never on the Odoo server |

   **Set the API key** on the Anthropic records. The *model* field is free text: use any model the provider
   accepts. Switch the *type* to "OpenAI-compatible" to use OpenAI, Azure OpenAI, OpenRouter, vLLM or Ollama
   (set the base URL). Use **Test connection** on each record. Prices per 1M tokens drive the per-session cost.
   Mock providers (archived) give a fully offline demo.
2. **Templates** – link a template to job positions; edit section guidance, time limits, weights and bands.
3. **Question bank** – use *Generate pool questions*; problems are validated in the sandbox (all four reference
   solutions must pass) and then need admin approval. Target: 50 approved per type.
4. **Settings** (Recruitment → Settings → AI Interview): languages, simultaneous interviews (queue),
   auto-invite, TTS voice, retention per data type.
5. **Consent notice** – edit wording; accepted versions are immutable (a new version is created).

See `services/docker-compose.example.yml` for the self-hosted Whisper / Kokoro / Judge0 services.

## Use

* Applicant → **Send AI Interview** (or a campaign → *Invite applicants*). The candidate receives an expiring link.
* Candidate: consent → mic/browser check → Written English → Coding → Learn and apply → Voice interview → submit.
* Scoring runs in the background (cron, triggered on submit). The applicant gets an *AI Interview* tab,
  chatter messages and a review activity.
* **Campaign dashboard** and **candidate dashboard** (scores vs campaign average, evidence, typing replay,
  audio, integrity timeline, review panel, PDF).
* A reviewer must confirm the band and decision before the applicant can move stage.

## Notes / deviations

* Odoo 19 removed the `hr.candidate` model. Interview history is linked across applications via the applicant's
  contact and normalised e-mail (same smart button behaviour as the FRD describes).
* The local subprocess sandbox exists for development only and must be explicitly enabled.

## Tests

```bash
odoo-bin -d <db> -u linda_ai_interview --test-enable --test-tags /linda_ai_interview --stop-after-init
```
Browser smoke tests need Chrome and the `websocket-client` package.
