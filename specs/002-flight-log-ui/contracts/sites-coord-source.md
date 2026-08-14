# Behavioral change: `POST /api/sites` and `PUT /api/sites/{id}`

No schema change — `SiteCreate`/`SiteUpdate`/`SiteOut` are unchanged. Behavioral change only:

- `POST /api/sites`: if the request body includes a non-null `lat` and/or `lon`, the created row's
  `coord_source` is set to `"manual"` server-side.
- `PUT /api/sites/{id}`: if `lat` and/or `lon` is present among the fields being updated
  (`exclude_unset=True`), the row's `coord_source` is set to `"manual"` server-side alongside them.
- `coord_source` remains absent from both `SiteCreate` and `SiteUpdate` — it is never accepted from the
  client, the same pattern as `owner_id`. See `research.md` for why.
