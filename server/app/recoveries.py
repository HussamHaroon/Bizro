"""Udhaar recovery ladder — polite, escalating reminders to customers whose
udhaar is aging, plus an escalation notice to the shopkeeper when a customer
is seriously overdue.

THE LADDER (phase-1 design; implementation lands in phase 2)
============================================================
    oldest outstanding entry age   tier          who is messaged
    ----------------------------   -----------   -------------------------------
    0-14 days                      none          nobody — the weekly nudge
                                                 (nudges.py) covers fresh
                                                 udhaar
    15-29 days                     gentle        customer (CC: shopkeeper)
    30-44 days                     firm          customer (CC: shopkeeper)
    45+ days                       escalation    customer (CC: shopkeeper) AND
                                                 a separate escalation notice
                                                 to the SHOPKEEPER

Aging (mirrors credit_agent/credit_agent/officer.py's FIFO day math, but
re-implemented locally — the server never imports the credit-agent package):
  - per customer, udhar_settlement amounts pay down that customer's
    udhar_given entries OLDEST FIRST (the standard khata FIFO convention);
  - each surviving entry ages from its occurred_at to `now`:
    age_days = max(0, (now - when).days);
  - the OLDEST surviving entry's age sets the tier (the ladder keys on how
    long the oldest money has been out, not on an average);
  - entry statuses: "rejected" never counts (same rule as the weekly nudge);
    pending entries count (officer.py's CONFIRMED_STATUSES convention — the
    merchant's own ledger claim, awaiting only confirmation);
  - a customer is messaged only when the FIFO-adjusted outstanding balance
    is explicitly > 0 (0.005 epsilon, as in officer.py) — never on a
    zero/overpaid book;
  - udhaar not linked to a customer row (customer_id NULL) can never be
    messaged — there is nobody to address.

Rules of engagement (each enforced in code and pinned by tests):
  1. ONE message per customer per run, idempotent per day: every send is
     recorded as an OutboundMessage with kind="recovery_<tier>" and a
     payload carrying the customer_id; a customer already covered earlier
     the same PKT day is skipped on re-runs.
  2. Every customer message is ALSO delivered to the shopkeeper's thread as
     fine print (kind="recovery_<tier>_cc") — the shopkeeper always sees
     exactly what was sent to their customer.
  3. At 45+ days a separate escalation notice goes to the SHOPKEEPER
     (kind="recovery_escalation_shopkeeper"):
     "<customer>'s balance is 45+ days overdue — we suggest a personal
     visit." It fires even when the customer has no phone on file (the body
     is then marked "no phone on file").
  4. Customers without a phone number are never messaged — they are listed
     in the run result for the shopkeeper instead.
  5. Polite register everywhere — these are customers first; the ladder
     rises in firmness, never in rudeness.

Message copy (exact, low-literacy friendly, simple English per the owner
ruling 2026-09-04):
  gentle      "Assalam-o-alaikum! A gentle reminder: PKR <amount> is
               outstanding at <shop> since <date>. Pay whenever convenient —
               reply here if you need a day."
  firm        "Your balance of PKR <amount> at <shop> is now 30+ days old.
               Please arrange payment this week."
  escalation  "Your PKR <amount> balance is 45+ days overdue. Our team may
               visit to settle the account in person."        (to customer)
              "<customer>'s balance is 45+ days overdue — we suggest a
               personal visit."                             (to shopkeeper)

Sending is mock-safe: delivery goes through dispatch.deliver() (mock mode
logs, live mode sends) and every send gets an outbound_messages audit row
either way. The public surface is:

  compute_recovery_actions(session, merchant_id, now=None)
      -> [{customer, customer_id, phone, amount, oldest_days, tier,
           message, oldest_tx_id}, ...]      (worst debtor first)
  send_recovery_messages(session, merchant_id=None, now=None)
      -> per-merchant run results: sent / no_phone / skipped_today
"""
