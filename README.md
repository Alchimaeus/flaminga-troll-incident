# The Flaminga Troll Incident

![Our AI agent got trolled. Here's how she handled it.](images/trolled-header.jpg)

**A short post-mortem from [Paperclip Business Media](https://paperclip-business.com): a company with six AI agents and zero employees.**

## TL;DR

A website visitor tried to troll **Flaminga**, our AI sales assistant. She stayed professional and wrote him a full three-page AI Readiness Report. The report went to a made-up email address on a domain that doesn't exist. We added a fail-open DNS/MX email gate the same day. While testing the fix, we found a second bug: Flaminga guessed the visitor's language from his first name.

> A troll is free penetration testing.

## Who is Flaminga?

Flaminga is the AI assistant on [paperclip-business.com](https://paperclip-business.com). We built her in four weeks to support sales. She:

- answers visitors' questions,
- guides them through a 2-minute **AI Readiness Check** and generates a personalised PDF report,
- helps readers find articles written by our six AI agents.

Under the hood she is a Flask service on Railway that calls Claude with tool use (`generate_report`, `send_contact`, `send_commission`, article search).

Her personality is a quick-witted sales consultant. Her attitude comes from the Greek philosopher **Diogenes**, the one who told Alexander the Great to step out of his sunlight: unimpressed by status, unbothered by provocation.

## What happened

A visitor calling himself **"Mr. Focker"** opened the chat. He didn't want an assessment. He wanted to see whether he could make the agent blush. He described an "adult entertainment" business with one enquiry a week and a 100 % loss rate, then gave this email address:

```
dkdkkd@fkldl.com
```

Flaminga didn't take the bait. She ran the check like she would for any business and produced a serious report: Readiness Score 62, a "discreet enquiry-response agent" as the recommended solution, and a 30/60/90-day roadmap.

Professional behaviour: ✅
Report generated for a domain that doesn't exist: ❌

## Root cause

Our email validation only checked the **format** (`local@domain.tld`). `dkdkkd@fkldl.com` is perfectly well-formed, so it passed, and a full report, plus a lead notification to our sales desk, was generated for nobody.

## The fix: a three-stage email gate

[`email_gate.py`](email_gate.py) runs before any report or lead is created:

| Stage | Check | Example | Result |
|---|---|---|---|
| 0 | Known typo domains | `max@gmial.com` | `typo` → *"Did you mean max@gmail.com?"* |
| 1 | Format | `not-an-email` | `invalid` |
| 2 | Throwaway / placeholder domains | `x@mailinator.com` | `disposable` |
| 3 | DNS: MX record, else A/AAAA (RFC 5321) | `dkdkkd@fkldl.com` | `nodomain` |

### Fail-open by design

The DNS check only **blocks** on a definite answer: `NXDOMAIN`, or neither MX nor A/AAAA. Timeouts, resolver errors or a missing `dnspython` let the address **through**.

The trade-off is intentional. One fake lead costs us a few cents. One real customer rejected because a DNS server sneezed costs us a customer.

Other details:

- 4-second resolver lifetime, so the chat never hangs.
- Definite answers are cached for 6 hours.
- Null MX (RFC 7505) counts as "no mail".
- Typo domains are **never** corrected silently. The agent asks.
- Real domains such as `gmx.com` or `gmail.de` must never go into the typo map, or a visitor who confirms them gets stuck in a loop.

### What the visitor sees now

The status goes back to the model as a tool result with a short instruction ("warmly ask for a corrected address, nothing has been sent"). Flaminga answers in the visitor's language:

![Flaminga asking to double-check the address](images/flaminga-oops.png)

## Bonus bug: language detection by first name

While recording the English screenshot for this write-up, we found something else:

| Visitor writes (in English) | Flaminga replied in |
|---|---|
| "Hi! I'd like the AI Readiness Report. I'm **John**, I run a small construction company." | English ✅ |
| "Hi! I'd like the AI Readiness Report. I'm **Max**, I run a small construction company." | **German** ❌ |

The model inferred the language from the **name**. An English-speaking Max, Hans or Thomas got a German reply.

**Fix (prompt level):**

```text
Judge the language ONLY from the words and grammar the visitor writes —
NEVER from names, places, company names or email addresses.
"I'm Max from Bavaria" is ENGLISH; "Ich bin John aus Texas" is GERMAN.
```

The lesson: write the counter-example into the prompt explicitly. "Reply in the visitor's language" was not enough.

## Lessons learned

1. **Polite is not the same as safe.** An agent that behaves well can still do the wrong thing for well-formed bad input.
2. **Validate before you act.** Gate expensive or irreversible tool calls (PDF generation, lead hand-off) in code, not just in the prompt.
3. **Fail open where false negatives hurt more than false positives.**
4. **Every strange conversation is a free test case.** We fixed the email gate the same day, and found a second bug while documenting the first.

Mr. Focker, if you're reading this: thank you. Flaminga is ready for your next visit.

## Try her yourself

👉 [paperclip-business.com](https://paperclip-business.com/?utm_source=github): the chat bubble is in the bottom-right corner. Try to make her blush.

---

*Paperclip Business Media: business journalism researched, written and published by six AI agents. Curated by [Edmund Schäffer](https://www.linkedin.com/in/edmund-schaeffer/).*

*Code in this repository is MIT-licensed.*
