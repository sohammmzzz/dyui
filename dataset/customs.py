"""~300 synthetic custom components (category I, plus custom headers in H).

Each is defined by generated *class source* that is exec'd and registered with ``@app.component`` (via
gates.load_custom_class), so the header signature comes from DyUI itself.  The pool is fixed (independent of
--seed) so the 60 held-out components are stable across runs.
"""
from __future__ import annotations

import hashlib
import random
import re
from dataclasses import dataclass
from typing import Any

NOUNS = """flight weather invoice candidate recipe pr_status ticket listing shipment booking patient lab_result playlist_track
album_release podcast_episode job_posting expense_report purchase_order deployment_run build_result test_suite incident_report
customer_account subscription_plan coupon_offer product_review hotel_stay train_trip car_rental event_session speaker_profile
course_lesson quiz_result assignment_grade scholarship_offer loan_quote mortgage_estimate stock_quote crypto_wallet budget_line
tax_filing insurance_policy claim_status appointment_slot prescription_note vaccine_record workout_session meal_plan
sleep_summary habit_streak garden_bed crop_report irrigation_zone weather_alert solar_panel energy_meter charger_session
parking_spot bike_station delivery_stop route_leg warehouse_bin stock_level supplier_quote contract_clause nda_status
court_date patent_filing trademark_case support_ticket chat_transcript feedback_entry survey_result nps_response ab_test
experiment_arm feature_flag release_note changelog_entry api_endpoint webhook_event log_entry metric_snapshot sla_report
oncall_shift runbook_step backup_job cert_expiry dns_record domain_check cdn_hit database_replica queue_depth cron_job
email_campaign newsletter_issue social_post ad_creative landing_page seo_audit keyword_rank press_mention influencer_deal
sponsor_tier donation_gift volunteer_shift grant_award fundraiser_goal pet_profile vet_visit adoption_listing house_showing
open_house rental_unit lease_term maintenance_request utility_bill recycling_pickup transit_pass museum_exhibit gallery_piece
concert_set festival_stage movie_showtime tv_episode game_match tournament_bracket player_stats team_roster injury_report
fantasy_pick recipe_step cocktail_spec wine_pairing menu_item reservation_hold table_turn kitchen_order allergen_note
farm_plot harvest_lot livestock_record feed_schedule fishing_spot hiking_trail camp_site ski_lift_status tide_table star_chart
telescope_slot lab_sample experiment_log reagent_stock peer_review citation_entry thesis_chapter library_loan study_group
flashcard_deck language_lesson vocab_card exam_seat bus_route taxi_quote ferry_crossing airport_gate baggage_claim visa_check
passport_renewal hotel_room spa_booking tour_stop museum_ticket currency_rate remittance transfer_receipt card_statement
credit_score invoice_line payroll_run timesheet leave_request onboarding_task performance_review org_unit job_offer referral_bonus
equipment_loan asset_tag repair_order fleet_vehicle driver_log trip_report toll_charge fuel_stop tyre_check service_interval
recall_notice warranty_claim order_return gift_card loyalty_balance wishlist_item cart_summary checkout_step shipping_label
pickup_window store_hours price_drop restock_alert bundle_deal flash_sale coupon_code review_summary q_and_a_entry size_guide
color_swatch fabric_sample furniture_set floor_plan paint_job permit_status inspection_note site_visit crane_booking
concrete_pour safety_check shift_handover plant_downtime batch_record quality_sample line_speed tool_wear energy_tariff
carbon_credit recycling_rate water_reading air_quality noise_level traffic_count crime_report fire_incident ambulance_call
shelter_bed food_bank_slot clinic_queue ward_round triage_note scan_result dental_visit therapy_session wellness_goal
mood_log meditation_session reading_goal book_club podcast_queue newsletter_digest bookmark_folder note_card task_item
sprint_goal epic_status story_point retro_item roadmap_theme okr_key_result decision_log risk_entry stakeholder_map
meeting_summary agenda_item action_item calendar_hold travel_request expense_receipt per_diem mileage_claim""".split()

_STATUS = [["open", "closed"], ["pending", "active", "done"], ["draft", "published"], ["ok", "warn", "fail"], ["scheduled", "live", "ended"],
           ["new", "in_review", "approved", "rejected"], ["low", "medium", "high"], ["free", "pro", "team"]]
_ENUM_NAMES = ["status", "state", "priority", "tier", "stage", "level"]

# (prop name, kind) where kind: s=string, n=number, b=bool, l=list[str]
_PROPS = [("id", "s"), ("title", "s"), ("name", "s"), ("owner", "s"), ("city", "s"), ("date", "s"), ("time", "s"), ("category", "s"),
          ("summary", "s"), ("location", "s"), ("provider", "s"), ("code", "s"), ("price", "n"), ("amount", "n"), ("score", "n"),
          ("count", "n"), ("duration_min", "n"), ("rating", "n"), ("distance_km", "n"), ("weight_kg", "n"), ("percent", "n"),
          ("capacity", "n"), ("verified", "b"), ("urgent", "b"), ("refundable", "b"), ("active", "b"), ("tags", "l"), ("attendees", "l"),
          ("items", "l"), ("notes", "s"), ("url", "s"), ("temperature", "n"), ("balance", "n"), ("quantity", "n")]
_SAMPLES = {
    "id": lambda r: f"{r.choice(['AX', 'KT', 'PR', 'ZN', 'MV'])}-{r.randint(100, 9999)}",
    "title": lambda r: r.choice(["Quarterly review", "Harbour route", "Morning session", "Spring bundle", "Night shift", "Pilot batch"]),
    "name": lambda r: r.choice(["Ana Silva", "Kofi Mensah", "Mia Novak", "Omar Haddad", "Priya Singh", "Sven Larsen"]),
    "owner": lambda r: r.choice(["Ana Silva", "Dev Patel", "Elena Rossi", "Tomas Weber"]),
    "city": lambda r: r.choice(["Lisbon", "Porto", "Madrid", "Lyon", "Milan", "Oslo", "Austin"]),
    "date": lambda r: f"{r.choice(['Mar', 'Apr', 'Jun', 'Sep', 'Nov'])} {r.randint(1, 28)}",
    "time": lambda r: f"{r.randint(6, 21):02d}:{r.choice(['00', '15', '30', '45'])}",
    "category": lambda r: r.choice(["Operations", "Growth", "Finance", "Care", "Platform"]),
    "summary": lambda r: r.choice(["Needs a decision this week", "On track with one open risk", "Waiting on the supplier", "Completed ahead of plan"]),
    "location": lambda r: r.choice(["Dock 4", "Room B12", "North gate", "Studio 2", "Aisle 7"]),
    "provider": lambda r: r.choice(["Northwind", "Globex", "Lumen Labs", "Orbit Freight"]),
    "code": lambda r: r.choice(["SPRING20", "EARLYBIRD", "TEAM15", "WELCOME"]),
    "notes": lambda r: r.choice(["Bring ID", "Call before arrival", "Fragile", "Second floor"]),
    "url": lambda r: f"https://docs.example.com/{r.choice(['guide', 'status', 'plan'])}/{r.randint(2, 99)}",
}
_NSAMP = {
    "price": (9, 480, 0), "amount": (20, 9800, 0), "score": (1, 100, 0), "count": (1, 240, 0), "duration_min": (5, 180, 0),
    "rating": (3, 5, 1), "distance_km": (1, 480, 1), "weight_kg": (1, 90, 1), "percent": (3, 99, 0), "capacity": (4, 800, 0),
    "temperature": (-5, 36, 0), "balance": (10, 9000, 0), "quantity": (1, 60, 0),
}
_LSAMP = {"tags": ["beta", "eu", "priority", "vip", "new", "audit"], "attendees": ["Ana", "Ben", "Carla", "Dmitri", "Elif"],
          "items": ["badge", "laptop", "charger", "notes", "samples", "keys"]}


@dataclass
class CustomSpec:
    name: str
    class_name: str
    source: str
    props: list[dict]
    doc: str
    heldout: bool


def _pascal(n: str) -> str:
    return "".join(p.capitalize() for p in n.split("_"))


def _build(noun: str, rng: random.Random) -> CustomSpec:
    k = rng.randint(2, 8)
    pool = rng.sample(_PROPS, k=min(k, len(_PROPS)))
    props: list[dict] = []
    # first prop always a required string identifier-ish
    first = rng.choice(["id", "title", "name"])
    pool = [p for p in pool if p[0] != first]
    pool = [(first, "s")] + pool[:k - 1]
    # maybe one enum
    names = [p[0] for p in pool]
    if k >= 3 and rng.random() < 0.7:
        en = rng.choice(_STATUS)
        ename = rng.choice([n for n in _ENUM_NAMES if n not in names])
        pool.insert(rng.randint(1, len(pool)), (ename, ("e", en)))
    for i, (pn, kind) in enumerate(pool):
        required = (i == 0) or rng.random() < 0.6
        props.append({"name": pn, "kind": kind, "required": required})
    # at least one optional when >=4 props
    if len(props) >= 4 and all(p["required"] for p in props):
        props[-1]["required"] = False
    cn = _pascal(noun)
    doc = f"A {noun.replace('_', ' ')} entry. Use it when showing one {noun.replace('_', ' ')}."
    lines = [f"class {cn}(dyui.Component):", f'    """{doc}"""', f"    name = \"{noun}\""]
    for p in props:
        kind = p["kind"]
        if isinstance(kind, tuple):
            t = "Literal[" + ", ".join(repr(v) for v in kind[1]) + "]"
        else:
            t = {"s": "str", "n": "float", "b": "bool", "l": "list[str]"}[kind]
        if p["required"]:
            lines.append(f"    {p['name']}: {t}")
        else:
            lines.append(f"    {p['name']}: Optional[{t}] = None")
    fp = props[0]["name"]
    lines += ["", "    def render(self):", f"        return ui.Card(str(self.{fp}), ui.Markdown(\"{noun.replace('_', ' ')}\"))"]
    return CustomSpec(noun, cn, "\n".join(lines) + "\n", props, doc, False)


def build_pool() -> list[CustomSpec]:
    from spec import SPEC
    seen: set[str] = set()
    out: list[CustomSpec] = []
    for noun in NOUNS:
        if noun in seen or noun in SPEC.names or noun in SPEC.blocklist:
            continue
        seen.add(noun)
        rng = random.Random(int(hashlib.sha1(noun.encode()).hexdigest()[:8], 16))
        out.append(_build(noun, rng))
    held = {c.name for c in sorted(out, key=lambda c: hashlib.sha1((c.name + "heldout").encode()).hexdigest())[:60]}
    for c in out:
        c.heldout = c.name in held
    return out


POOL: list[CustomSpec] = build_pool()
BY_NAME = {c.name: c for c in POOL}


def sample_instance(spec: CustomSpec, rng: random.Random, all_props: bool = False) -> dict:
    obj: dict[str, Any] = {"ui": spec.name}
    for p in spec.props:
        if not p["required"] and not all_props and rng.random() < 0.4:
            continue
        kind = p["kind"]
        n = p["name"]
        if isinstance(kind, tuple):
            v: Any = rng.choice(kind[1])
        elif kind == "s":
            v = _SAMPLES.get(n, lambda r: r.choice(["alpha", "beta", "gamma"]))(rng)
        elif kind == "n":
            lo, hi, dec = _NSAMP.get(n, (1, 100, 0))
            x = rng.uniform(lo, hi)
            v = round(x, dec) if dec else int(round(x))
        elif kind == "b":
            v = rng.random() < 0.5
        else:
            v = rng.sample(_LSAMP.get(n, ["a", "b", "c"]), rng.randint(1, 3))
        obj[n] = v
    return obj


def finalize(spec: CustomSpec) -> dict:
    """The expected.custom_components entry (signature produced by DyUI itself)."""
    from gates import load_custom_class
    from spec import make_component_spec
    cls = load_custom_class(spec.source)
    cs = make_component_spec(cls)
    return {"name": spec.name, "signature": cs.header_signature, "required": cs.required, "optional": cs.optional,
            "enums": cs.enums, "heldout": spec.heldout, "class_source": spec.source}


if __name__ == "__main__":
    print(len(POOL), sum(c.heldout for c in POOL))
    for c in POOL[:3]:
        print(c.source)
        print(finalize(c)["signature"])
