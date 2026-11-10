/*
MasterChanges.sql -- used by src/alerts/master_change.py

Returns one row per Master change that is due for notification:
  - the incoming contract has rank = rank_id and its vessel is active
  - it signed on (as per office) at least master_change_days ago,
    and no more than lookback_days ago
  - the incoming Master is still on board (no office sign-off, or one in the future)
  - no other Master is on board the same vessel
  - the preceding Master contract on the vessel belongs to a different person
    (a new contract for the same Master is not a change)

The preceding (outgoing) Master contract is the one on the same vessel that
signed on before the incoming contract and signed off most recently; a
contract that is still open counts as the most recent.

Bind parameters, supplied by MasterChangeAlert.fetch_data(): rank_id,
lookback_days, master_change_days.
Never put a colon directly in front of a word in this file, comments
included: SQLAlchemy text() would read it as a bind parameter.

Timestamps are stored without time zone and treated as UTC, consistent
with MasterChangeAlert.filter_data().

Parameters fetched from .env:
master_change_days = 14
lookback_days = 40
rank_id = 1
*/
WITH ref AS (
    SELECT (NOW() AT TIME ZONE 'UTC') AS now_utc
)
SELECT
    cc.id                                                       AS crew_contract_id,
    cc.crew_member_id                                           AS crew_member_id,
    v.id                                                        AS vessel_id,
    v.email                                                     AS vsl_email,
    v.name                                                      AS vessel,
    p.full_name                                                 AS full_name,
    cr.name                                                     AS rank,
    cc.sign_on_date_as_per_office                               AS sign_on_date,
    cc.sign_on_date_as_per_office
        + INTERVAL '1 day' * :master_change_days                AS due_date,
    prev.full_name                                              AS outgoing_master,
    prev.sign_off_date                                          AS outgoing_sign_off_date
FROM
    crew_contracts cc
CROSS JOIN
    ref
JOIN
    parties p
    ON p.id = cc.crew_member_id
JOIN
    vessels v
    ON v.id = cc.vessel_id
LEFT JOIN
    crew_ranks cr
    ON cr.id = cc.rank_id
LEFT JOIN LATERAL (
    -- Preceding Master contract: signed on before the incoming one, latest sign-off (open first)
    SELECT
        o.crew_member_id,
        op.full_name,
        o.sign_off_date_as_per_office AS sign_off_date
    FROM
        crew_contracts o
    LEFT JOIN
        parties op
        ON op.id = o.crew_member_id
    WHERE
        o.vessel_id = cc.vessel_id
        AND o.rank_id = cc.rank_id
        AND o.sign_on_date_as_per_office < cc.sign_on_date_as_per_office
    ORDER BY
        o.sign_off_date_as_per_office DESC NULLS FIRST,
        o.id DESC
    LIMIT 1
) prev ON TRUE
WHERE
    p.type = 'crew'
    AND v.active = 'true'
    AND cc.rank_id = :rank_id
    -- Due: master_change_days have passed since sign-on, within the lookback window
    AND cc.sign_on_date_as_per_office <= ref.now_utc - INTERVAL '1 day' * :master_change_days
    AND cc.sign_on_date_as_per_office >= ref.now_utc - INTERVAL '1 day' * :lookback_days
    -- Incoming Master still on board
    AND (
        cc.sign_off_date_as_per_office IS NULL
        OR cc.sign_off_date_as_per_office > ref.now_utc
    )
    -- No other Master on board the same vessel
    AND NOT EXISTS (
        SELECT 1
        FROM crew_contracts o
        WHERE
            o.vessel_id = cc.vessel_id
            AND o.rank_id = cc.rank_id
            AND o.crew_member_id <> cc.crew_member_id
            AND o.sign_on_date_as_per_office <= ref.now_utc
            AND (
                o.sign_off_date_as_per_office IS NULL
                OR o.sign_off_date_as_per_office > ref.now_utc
            )
    )
    -- If the preceding Master contract on the vessel belongs to the same person, it is not treated as a change. 
    -- To be notified anyway, delete the line:
    -- AND prev.crew_member_id IS DISTINCT FROM cc.crew_member_id
ORDER BY
    cc.sign_on_date_as_per_office DESC;
