"""
Per-account starter data for a newly self-registered pilot (v0.9).

Not a startup seeder (see database/db.py's _seed_regions for that pattern, which is
shared/global reference data) — this runs once, from the register() handler, guarded by
`users.seeded_at IS NULL`. A self-registered account previously landed with zero flight
categories and no way to log a flight, since `flights.category_id` is NOT NULL — this closes
that gap. See specs/007-sharing-public-readiness/research.md for why five generic English
categories, not the 12 legacy German ones (this pilot's own personal history, several of them
jurisdiction-specific), are seeded here.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from flightlog.database.models import FlightCategory, User, utcnow

logger = logging.getLogger(__name__)

# (name, slug, is_hike_fly, is_training) — slug matches categories.py's own _slugify() output
# for each name, computed once here rather than imported, since these five are fixed strings.
_STARTER_CATEGORIES = [
    ("Thermal", "thermal", False, False),
    ("Soaring", "soaring", False, False),
    ("XC", "xc", False, False),
    ("Hike&Fly", "hike-fly", True, False),
    ("Sled run", "sled-run", False, False),
]


def seed_starter_categories(db: Session, user: User) -> None:
    """
    Idempotent: a no-op if `user.seeded_at` is already set. Writes through the same
    `FlightCategory` model every manual `POST /api/categories` creation uses, so every
    existing validation / editability the pilot already has for a category applies here
    unchanged (FR-011) — this is a data seed, not a special-cased row shape.
    """
    if user.seeded_at is not None:
        logger.info("Starter categories already seeded for %s, skipping", user.id)
        return

    for order, (name, slug, is_hike_fly, is_training) in enumerate(_STARTER_CATEGORIES):
        db.add(
            FlightCategory(
                owner_id=user.id,
                name=name,
                slug=slug,
                is_hike_fly=is_hike_fly,
                is_training=is_training,
                sort_order=order,
            )
        )

    user.seeded_at = utcnow()
    logger.info("Seeded %d starter categories for %s", len(_STARTER_CATEGORIES), user.id)
