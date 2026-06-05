#!/usr/bin/env python3
"""
reconcile.py — guardrail for DERIVED figures in a German tax analysis.

Why this exists
---------------
Step 3 of the workflow recomputes the figures that are PRINTED on the Bescheid
(the calculation_chain). But the report also shows DERIVED / aggregate figures
that appear on no document: the refund->payment "swing", deltas between two
assessments, "this costs you X", netted positions. Those were once produced ad
hoc and checked tautologically (assert X == the same X), which let a double-count
slip through: a refund->payment "swing" of 10.350,76 € when the true figure was
7.341,76 € — because the 7.341,76 € payment demand ALREADY clawed back the
3.009 € refund, and the refund was then added a second time.

The rule this script enforces
------------------------------
Never assert a derived value against itself. Every derived figure must be
computed from primitives **two (or more) independent ways that must agree**.
For an Änderungsbescheid, the refund->payment swing must satisfy, simultaneously:

    swing = amended_net - initial_net            # net settlement positions
          = cash_payable_now (incl. clawback)    # what the FA actually demands
          = Δ festgesetzt - Δ credits            # extra tax minus extra credits

If those three do not match within tolerance, it is a bug — stop.

Signed convention: a refund is NEGATIVE, a payment is POSITIVE (this mirrors
"verbleibende Steuer": negative = money back to the taxpayer).

Usage
-----
    python3 reconcile.py <facts.json>                       # single assessment
    python3 reconcile.py <initial_facts.json> <amended_facts.json>   # amendment

Exits non-zero on any mismatch. Dependency-light (stdlib only).
"""

import json
import sys

TOL = 0.005


class ReconcileError(AssertionError):
    """Figures were computed but two independent derivations DISAGREE."""
    pass


class DataError(ReconcileError):
    """The data needed for a check is MISSING or broken, so the figure cannot be
    verified at all. Fail closed: never pass by silently reading zeros, and never
    present an unverified calculation to the user."""
    pass


def eur(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"


def _num(value, where):
    """Require a present, numeric (non-null) value. Raise DataError otherwise."""
    if value is None:
        raise DataError(f"missing/null value at {where} — cannot verify (fail closed).")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"non-numeric value {value!r} at {where} — cannot verify (fail closed).")
    return float(value)


def equal_ways(label, ways, tol=TOL):
    """Core anti-tautology helper.

    `ways` is a dict {derivation_name: value}. Asserts every value agrees with
    the others. Raises ReconcileError (with a readable diff) if not — and refuses
    to "pass" a figure that was only computed one way (that would be a self-check).
    """
    items = list(ways.items())
    if len(items) < 2:
        raise ReconcileError(
            f"[{label}] needs >=2 INDEPENDENT derivations to reconcile, got {len(items)}. "
            f"A single formula checked against itself is not a verification."
        )
    base_name, base_val = items[0]
    bad = [(n, v) for n, v in items[1:] if abs(v - base_val) > tol]
    print(f"  [{label}]")
    for n, v in items:
        print(f"      {n:<34} = {eur(v)}")
    if bad:
        raise ReconcileError(
            f"[{label}] derivations DISAGREE: "
            + "; ".join(f"{base_name}={eur(base_val)} vs {n}={eur(v)} (Δ {eur(v-base_val)})"
                        for n, v in bad)
        )
    print(f"      -> reconciled: {eur(base_val)}  ({len(items)} independent ways agree)")
    return base_val


# ---------- helpers to read the facts.json result block (fail-closed) ----------

def _require_per_tax(facts, name):
    """Return the validated abrechnung.per_tax rows, or raise DataError.

    Every row must carry numeric festgesetzt / vorausgezahlt / verbleibend — a
    missing or null field means we cannot reconcile the settlement, so we refuse
    to proceed rather than read zeros and pass vacuously."""
    result = facts.get("result")
    if not isinstance(result, dict):
        raise DataError(f"{name}: no 'result' object — cannot reconcile.")
    per_tax = result.get("abrechnung", {}).get("per_tax")
    if not isinstance(per_tax, list) or not per_tax:
        raise DataError(
            f"{name}: result.abrechnung.per_tax is missing/empty — the settlement "
            f"(festgesetzt/vorausgezahlt/verbleibend) cannot be reconciled. Populate it (fail closed)."
        )
    for row in per_tax:
        tax = row.get("tax", "?")
        for field in ("festgesetzt", "vorausgezahlt", "verbleibend"):
            _num(row.get(field), f"{name}: abrechnung.per_tax[{tax}].{field}")
    return per_tax


def _festgesetzt_total(facts, name):
    return sum(_num(r.get("festgesetzt"), f"{name}.festgesetzt") for r in _require_per_tax(facts, name))


def _credits_total(facts, name):
    """Everything already paid/credited (wage tax + capital-gains tax + advances)."""
    return sum(_num(r.get("vorausgezahlt"), f"{name}.vorausgezahlt") for r in _require_per_tax(facts, name))


def _net_position(facts, name):
    """verbleibende Steuer summed across taxes; negative = refund, positive = owed.
    The assessment's OWN result, BEFORE any clawback bookkeeping."""
    return sum(_num(r.get("verbleibend"), f"{name}.verbleibend") for r in _require_per_tax(facts, name))


def _signed_refund_or_payment(facts, name):
    """Documented cash movement; raise DataError if the block is malformed."""
    rp = facts.get("result", {}).get("refund_or_payment")
    if not isinstance(rp, dict) or "amount" not in rp:
        raise DataError(f"{name}: result.refund_or_payment(.amount) missing — cannot verify the cash movement.")
    amt = _num(rp.get("amount"), f"{name}: refund_or_payment.amount")
    direction = rp.get("direction")
    if direction not in ("refund", "payment", "none"):
        raise DataError(f"{name}: refund_or_payment.direction = {direction!r} (expected refund/payment/none).")
    if direction == "refund":
        return -abs(amt)
    if direction == "none":
        return 0.0
    return abs(amt)


_CLAWBACK_KEY = "rueckforderung_erstattung_erstbescheid"


def _clawback(facts, name, prior_refund_existed):
    """Prior refund reclaimed by this (amending) assessment.

    If the prior assessment refunded money, the clawback field MUST be present —
    otherwise we cannot confirm the amendment isn't double-counting it, so we fail
    closed rather than default to 0."""
    ext = facts.get("result", {}).get("extensions", {}) or {}
    if prior_refund_existed and _CLAWBACK_KEY not in ext:
        raise DataError(
            f"{name}: prior assessment refunded money, but result.extensions.{_CLAWBACK_KEY} "
            f"is missing — cannot confirm the refund is reclaimed exactly once (fail closed)."
        )
    return _num(ext[_CLAWBACK_KEY], f"{name}: extensions.{_CLAWBACK_KEY}") if _CLAWBACK_KEY in ext else 0.0


# ---------- single-assessment reconciliation ----------

def reconcile_single(facts, name="assessment"):
    """Returns the assessment's OWN net result (verbleibende Steuer):
    negative = refund, positive = owed. This is BEFORE any clawback bookkeeping.

    Two independent checks:
      (1) net identity:  festgesetzt - vorausgezahlt  ==  sum(verbleibend)
      (2) cash movement: signed(refund_or_payment)    ==  net + clawback
          (refund_or_payment is the CASH the FA moves now; for an Änderungs-
           bescheid that already includes reclaiming a prior refund, so it equals
           the assessment's net result PLUS the clawback — never net alone.)
    """
    print(f"\n=== Single-assessment reconciliation: {name} ===")
    festg = _festgesetzt_total(facts, name)
    credits = _credits_total(facts, name)
    net = _net_position(facts, name)
    signed_rp = _signed_refund_or_payment(facts, name)
    # A standalone file is its own assessment: a clawback is only expected when a
    # prior-refund field is explicitly recorded on THIS file.
    ext = facts.get("result", {}).get("extensions", {}) or {}
    clawback = _num(ext[_CLAWBACK_KEY], f"{name}: extensions.{_CLAWBACK_KEY}") if _CLAWBACK_KEY in ext else 0.0

    equal_ways(f"{name}: net result identity (refund<0 / owed>0)", {
        "festgesetzt - vorausgezahlt": festg - credits,
        "sum(verbleibend)": net,
    })
    equal_ways(f"{name}: cash movement = net + clawback", {
        "signed refund_or_payment": signed_rp,
        "net + clawback of prior refund": net + clawback,
    })
    return net


# ---------- amendment reconciliation (the case that bit us) ----------

def reconcile_amendment(initial, amended):
    print("\n=== Amendment reconciliation (refund -> payment swing) ===")
    init_net = reconcile_single(initial, "initial")
    am_net = reconcile_single(amended, "amended")

    # clawback of any prior refund: if the initial assessment refunded money,
    # that refund is reclaimed by the amendment. Derive it from the initial net,
    # and cross-check against the value RECORDED in the amended file (which must be
    # present when a prior refund existed — else _clawback fails closed).
    prior_refund_existed = init_net < -TOL
    clawback = max(0.0, -init_net)
    equal_ways("clawback of prior refund (derived vs recorded)", {
        "max(0, -initial_net)": clawback,
        "amended.extensions.rueckforderung": _clawback(amended, "amended", prior_refund_existed),
    })

    ext = amended.get("result", {}).get("extensions", {}) or {}

    # cash payable now: the documented "mithin zu wenig entrichtet" figures. This
    # MUST be an independent document source — do NOT fall back to (am_net+clawback),
    # which would make the no-double-count check tautological. Fail closed if absent.
    zu_wenig = [_num(v, f"amended: extensions.{k}") for k, v in ext.items()
                if k.startswith("zu_wenig_entrichtet")]
    if not zu_wenig:
        raise DataError(
            "amended: no result.extensions.zu_wenig_entrichtet* found — the cash the "
            "Finanzamt actually demands is not independently recorded, so the swing cannot "
            "be checked for a double-count. Add the documented 'zu wenig entrichtet' figures "
            "(fail closed; do not present the swing)."
        )
    cash_now_doc = sum(zu_wenig)

    # Δ festgesetzt - Δ credits
    d_festg = _festgesetzt_total(amended, "amended") - _festgesetzt_total(initial, "initial")
    d_credits = _credits_total(amended, "amended") - _credits_total(initial, "initial")

    print(f"\n  initial net = {eur(init_net)} | amended net = {eur(am_net)} | clawback of prior refund = {eur(clawback)}")

    ways = {
        "amended_net - initial_net": am_net - init_net,
        "cash payable now (incl. clawback)": am_net + clawback,
        "Δ festgesetzt - Δ credits": d_festg - d_credits,
    }
    # If the analysis stored a headline swing figure, include it as another
    # independent "way" so a hand-typed wrong number (e.g. a double-count) fails here.
    if "swing_vs_initial" in ext:
        ways["recorded swing_vs_initial"] = _num(ext["swing_vs_initial"], "amended: extensions.swing_vs_initial")
    swing = equal_ways("refund -> payment swing", ways)

    # Sanity invariant: the swing must equal the cash the FA actually demands
    # (because that demand already nets the prior refund). A swing LARGER than the
    # demand is the classic double-count.
    equal_ways(
        "swing == cash the Finanzamt demands (no double-count)",
        {"swing": swing, "cash payable (document)": cash_now_doc},
    )
    if swing > cash_now_doc + TOL:
        raise ReconcileError(
            f"swing {eur(swing)} exceeds the cash demanded {eur(cash_now_doc)} — "
            f"the prior refund (clawback) was almost certainly counted twice."
        )
    print(f"\n  OK: refund->payment swing = {eur(swing)} (equals cash demanded; no double-count).")
    return swing


def _load(path):
    """Load a facts.json, failing closed with a clear message on IO/JSON errors."""
    try:
        with open(path) as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise DataError(f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise DataError(f"{path} is not valid JSON: {e}")


def main(argv):
    if len(argv) == 2:
        reconcile_single(_load(argv[1]), argv[1])
    elif len(argv) == 3:
        reconcile_amendment(_load(argv[1]), _load(argv[2]))
    else:
        print(__doc__)
        return 2
    print("\nALL RECONCILIATIONS PASSED.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except DataError as e:
        print("\n" + "!" * 72, file=sys.stderr)
        print(f"CANNOT VERIFY — DATA MISSING OR BROKEN: {e}", file=sys.stderr)
        print("DO NOT present these figures to the user until the data is fixed.", file=sys.stderr)
        print("!" * 72, file=sys.stderr)
        sys.exit(2)
    except ReconcileError as e:
        print("\n" + "!" * 72, file=sys.stderr)
        print(f"RECONCILIATION FAILED (figures disagree): {e}", file=sys.stderr)
        print("DO NOT present these figures to the user — the calculation is wrong.", file=sys.stderr)
        print("!" * 72, file=sys.stderr)
        sys.exit(1)
