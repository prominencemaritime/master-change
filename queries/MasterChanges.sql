/*
vessel_name 	-> subject
full_name 		-> body
rank			-> body
sign_on_date	-> body
due_date		-> body
rank_id = '1'
lookback_days = 4
*/
SELECT
    cc.id AS crew_contract_id,
	--cc.rank_id,
	cc.crew_member_id AS crew_member_id,
	--cc.created_at,
    v.id as vessel_id,
	v.email AS vsl_email,
	v.name AS vessel,
    p.last_name AS surname,
	p.full_name AS full_name,
	cr.name AS rank,
	cc.sign_on_date_as_per_office AS sign_on_date,
	cc.sign_on_date_as_per_office + INTERVAL '14 days' AS due_date
FROM
	crew_contracts cc
LEFT JOIN
	crew_ranks cr
	ON cr.id = cc.rank_id
LEFT JOIN
	parties p
	ON p.id = cc.crew_member_id
LEFT JOIN
	vessels v
	ON v.id = cc.vessel_id
WHERE
	p.type = 'crew'
	AND v.active = 'true'
	AND cc.rank_id = '1'	--:rank_id --'1'
	AND cc.sign_on_date_as_per_office >= NOW() - INTERVAL '1 day' * 40	--:lookback_days
    AND NOW() >= cc.sign_on_date_as_per_office + INTERVAL '1 day'
ORDER BY
    cc.sign_on_date_as_per_office DESC;
