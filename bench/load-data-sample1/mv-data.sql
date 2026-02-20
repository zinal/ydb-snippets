UPSERT INTO dict_doctype(code, id, name) VALUES
  ('ED101', 'id-101', 'name-101'),
  ('ED108', 'id-108', 'name-108'),
  ('ED742', 'id-742', 'name-742'),
  ('ED999', 'id-999', 'name-999'),
  ('ED210', 'id-210', 'name-210'),
  ('ED275', 'id-275', 'name-275'),
  ('ED103', 'id-103', 'name-103'),
  ('ED113', 'id-113', 'name-113');

REPLACE INTO `mv/job_scans` (job_name, target_name, scan_settings, requested_at)
VALUES ('h1', 'mv1',
JsonDocument(@@{
    "rowsPerSecondLimit": 999999
}@@)
, CurrentUtcTimestamp());