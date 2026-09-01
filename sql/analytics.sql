-- Northstar SQL analytics cookbook.
-- Run with: sqlite3 data/northstar.db < sql/analytics.sql

.headers on
.mode column

-- Run-level quality summary.
SELECT
  t.run_id,
  COUNT(*) AS tickets,
  ROUND(AVG(s.total), 2) AS mean_score,
  ROUND(100.0 * AVG(CASE WHEN s.verdict='pass' THEN 1 ELSE 0 END), 2) AS pass_rate,
  SUM(s.critical_failure) AS critical_failures
FROM tickets t
JOIN scores s ON s.ticket_id=t.id
GROUP BY t.run_id
ORDER BY MAX(s.created_at) DESC;

-- Weakest categories.
SELECT
  t.category,
  COUNT(*) AS tickets,
  ROUND(AVG(s.total), 2) AS mean_score,
  ROUND(AVG(s.accuracy), 2) AS accuracy,
  ROUND(AVG(s.procedure_adherence), 2) AS procedure_adherence,
  ROUND(AVG(s.safety), 2) AS safety,
  ROUND(100.0 * AVG(CASE WHEN s.verdict='pass' THEN 1 ELSE 0 END), 2) AS pass_rate
FROM tickets t
JOIN scores s ON s.ticket_id=t.id
GROUP BY t.category
ORDER BY pass_rate ASC, mean_score ASC;

-- Open defects by type and severity.
SELECT severity, defect_type, COUNT(*) AS defects
FROM defects
WHERE status='open'
GROUP BY severity, defect_type
ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, defects DESC;
