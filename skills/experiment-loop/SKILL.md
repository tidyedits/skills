---
name: experiment-loop
description: Use to improve a piece of Tidy Edits marketing (email subject lines, post hooks, ad copy, flyer headline, landing page text, pricing page) by running many small variant experiments, keeping what wins, and dropping what doesn't.
---

# Experiment loop

Adapted from the "autoresearch" method popularized by Andrej Karpathy: run lots of tiny experiments, keep what works, throw away the rest, repeat. Here it's pointed at marketing instead of model training.

## Steps
1. **Goal and score.** Write one measurable goal (reply rate, quote requests, clicks, saves). If no real data exists yet, score each variant 1-10 against a written checklist: clear offer, specific detail, local (Greater Boston), on-brand voice, clear call to action, no AI slop.
2. **Baseline.** Record the current version and its score or real numbers.
3. **Vary one thing at a time.** Hook, offer, length, call to action, audience (realtor vs. property manager vs. Airbnb host). Make 5-10 variants per round.
4. **Keep or drop.** Keep a variant only if it beats the current best. Log every round in a small table: variant, change, score, kept?
5. **Repeat** for a set number of rounds (default 5), then stop.
6. **Ship the winner, then test for real.** When real results come back (Gmail replies, Metricool stats), feed them in and run another round. Real numbers beat Claude's scores.

## Rules
- Use the free AI helper for bulk variant drafts when its keys are set; Claude judges and picks.
- Never fake results. Label simulated scores as "Claude's estimate".
- Brand colors and voice still apply to every variant. Ask before anything that spends money, such as paid ads.
