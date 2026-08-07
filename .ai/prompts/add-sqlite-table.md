# Prompt: Add a New SQLite Table

Use this prompt when you need to persist new structured data.

> **No Alembic. No `.sql` files. No `_migrations` table.** See `.ai/instructions/02-backend-conventions.md`.
> New tables come from `create_all()`; only new *columns* need a guard.

---

Add a new SQLite table for `{entity}` following the project conventions:

1. **Define the ORM model** in `src/flightlog/database/models.py`:
   ```python
   class Entity(Base):
       __tablename__ = "entities"
       __table_args__ = (
           UniqueConstraint("owner_id", "name", name="uq_entity_owner_name"),
           Index("ix_entities_owner", "owner_id"),
       )

       id         = Column(String, primary_key=True, default=new_uuid)
       owner_id   = Column(String, ForeignKey("users.id", ondelete="CASCADE"),
                           nullable=False, index=True)
       name       = Column(String, nullable=False)
       created_at = Column(UtcDateTime, nullable=False, default=utcnow)
   ```

   - Every user-owned table carries `owner_id`, NOT NULL and indexed.
   - **Every datetime column is `UtcDateTime`, never `DateTime(timezone=True)`.** SQLite stores no
     offset, so the plain SQLAlchemy type silently returns a naive datetime on read — `UtcDateTime`
     (defined in `database/models.py`) re-attaches UTC. Use the module's `new_uuid` / `utcnow` helpers
     rather than inlining `uuid.uuid4()` / `datetime.now(timezone.utc)`.
   - Add the table to the module docstring's table list.

2. **Nothing else is needed for a new table.** `Base.metadata.create_all()` runs on every startup and
   creates only what is missing.

   **If you are adding a column to an existing table**, add an idempotent guard to
   `_run_column_migrations()` in `src/flightlog/database/db.py`:
   ```python
   cols = {row[1] for row in conn.execute(text("PRAGMA table_info(entities)")).fetchall()}
   if "new_col" not in cols:
       conn.execute(text("ALTER TABLE entities ADD COLUMN new_col TEXT"))
       conn.commit()
       logger.info("Migration: added entities.new_col column")
   ```

3. **If the table needs reference data**, add a seeder to `db.py` — a Python list plus an existence
   check, called from `init_db()`. Per-user seeding runs from the account-creation path instead,
   guarded by `users.seeded_at IS NULL`.

4. **Add the Pydantic schemas** (`Base` / `Create` / `Update` / `Out`) in `src/flightlog/models/`.
   `Update` models have every field `Optional` so `model_dump(exclude_unset=True)` gives true PATCH
   semantics. `Out` models set `model_config = {"from_attributes": True}`.

5. **Add CRUD endpoints** in the appropriate router (or create one — see `add-api-router.md`). Include
   the `_get_own_{entity}()` ownership helper: 404 if missing, 403 if not yours.

6. **Add tests** — at minimum: create, list scoped to owner, another user's row returns 404, and the
   `owner_id` in a request body is ignored.

7. **Update `.ai/context/architecture.md`** — add the table to the "SQLite Tables" table with its
   milestone, and document any non-obvious design decision and what breaks if it is "fixed".

8. **Sync**: run `.ai/prompts/sync.md`.
