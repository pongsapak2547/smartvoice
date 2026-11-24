ALTER TABLE calls ADD COLUMN case_link_status TEXT CHECK (case_link_status IN ('pending','linked','failed','not_required'));
ALTER TABLE calls ADD COLUMN case_link_plan TEXT;
ALTER TABLE calls ADD COLUMN case_link_error TEXT;
ALTER TABLE calls ADD COLUMN case_link_updated_at TEXT;
UPDATE calls SET case_link_status = CASE
    WHEN case_id IS NOT NULL AND EXISTS (
        SELECT 1 FROM cases cs JOIN call_customer_links l ON l.customer_id = cs.customer_id
        JOIN customers c ON c.id = l.customer_id
        WHERE cs.id = calls.case_id AND l.call_id = calls.id AND c.deleted_at IS NULL
    ) AND (SELECT COUNT(DISTINCT customer_id) FROM call_customer_links WHERE call_id = calls.id) = 1 THEN 'linked'
    WHEN case_id IS NULL AND NOT EXISTS (SELECT 1 FROM call_customer_links WHERE call_id = calls.id) THEN 'not_required'
    ELSE 'pending' END,
    case_link_updated_at = updated_at
WHERE status = 'done';
