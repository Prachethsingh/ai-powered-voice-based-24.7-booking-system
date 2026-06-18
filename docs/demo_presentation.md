# Demo Presentation Script
## AI-Powered 24/7 Call Ordering System — ~6 Minutes

### [0:00] Introduction (30s)
"This is ai powered voice based 24.7 booking system — a CPU-only voice ordering system for businesses that
currently take orders by phone manually. No GPU, no cloud AI API calls, runs on a
single low-cost VM."

### [0:30] The Problem (30s)
"Today, a customer calling in means a staff member has to answer, listen, write down
items, double-check quantities, and manually enter the order somewhere. That's slow,
error-prone, limited to working hours, and gives the business zero visibility into
order patterns."

### [1:00] The Approach (45s)
"Rather than reaching for a large hosted AI model — which the brief explicitly rules
out for cost and resource reasons — this system gets reliability from *structure*
instead of *scale*: a small CPU-only speech model, a small CPU-only language model run
through a chain-of-thought prompt, and a deterministic regex cross-check that votes
against the model's output. When the two disagree, the system asks the caller to
repeat rather than guessing."

### [1:45] Live Demo (2 minutes)
"Let me walk through what happens on an actual call:
1. Customer dials in — Asterisk answers instantly, no working-hours restriction.
2. They say: 'I want 2 kilos rice and one liter milk, my number is 9876543210.'
3. Whisper transcribes it in under a second.
4. The ensemble pipeline extracts the phone number and items, cross-checks them, and
   confirms high confidence.
5. The order validator checks the phone format, checks for duplicates, checks rate
   limits — all in well under 100 milliseconds.
6. The customer hears: 'Thank you! Your order for rice 2kg and milk 1L has been
   confirmed.'
7. Switch to dashboard — the order appears live, with the customer's phone number
   masked for privacy, items, and status. The agent can mark it confirmed then
   fulfilled here."

### [3:45] Concurrency (45s)
"This isn't a single-caller demo trick — the backend runs a bounded worker pool, so 10
to 20 callers ringing in at once are queued and processed by parallel workers instead
of overwhelming the CPU or crashing. Show the capacity endpoint or dashboard metrics
tab — you can see active calls, queue depth, and average wait time live."

### [4:30] Security (45s)
"Every phone number is encrypted at rest with AES-128 before it touches the database —
the dashboard only ever shows a masked version. SQL queries are fully parameterized.
Rate limiting and 5-minute deduplication prevent accidental double-orders. The
WebSocket dashboard requires origin and token verification. None of this is bolted on
after the fact — it's the database layer itself."

### [5:15] Resource Footprint (30s)
"Total model footprint: about 275 megabytes across both the speech model and the
language model — combined, smaller than a single photo album on your phone. No GPU
anywhere in this stack. Estimated hosting cost: roughly five to seven thousand rupees a
month on a small cloud VM."

### [5:45] Close (15s)
"That's ai powered voice based 24.7 booking system — automated, 24/7, CPU-only, and built to scale out
horizontally if order volume grows. Happy to take questions."

---

## Anticipated Q&A

**Q: How accurate is the small model really, compared to something like ChatGPT?**
A: For this specific narrow task — extracting a phone number and item list from short
spoken sentences — the ensemble approach (chain-of-thought + self-consistency voting +
regex cross-check) closes most of the practical gap, because phone numbers are a closed
format where a deterministic extractor genuinely outperforms a generative model. See
`docs/accuracy_approach.md` for the full breakdown. It is not a claim of general
reasoning parity — it's a claim of reliability on this specific, well-defined task.

**Q: What happens if the system can't understand the caller?**
A: It doesn't guess. Low-confidence extractions trigger a spoken re-ask — "Sorry, can
you repeat your phone number?" — the same way a human staff member would.

**Q: What if 50 people call at once, beyond the 20 you're scaled for?**
A: The queue is sized with headroom (40 slots) above the target concurrency. Beyond
that, callers hear a polite "system is busy" message rather than the call hanging or
the server crashing — and the architecture scales horizontally (add a second VM)
without code changes, since all state lives in Redis/SQLite rather than in-process.

**Q: Why not just use Twilio, Dialogflow, or a hosted LLM API?**
A: Per-call API costs and per-minute telephony AI pricing scale linearly with call
volume and recur forever; this stack's cost is a flat, predictable VM bill regardless
of volume, and there's no per-call vendor dependency or data leaving the business's own
infrastructure.
