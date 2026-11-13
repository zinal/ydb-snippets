(
SELECT COUNT(*) FROM `replication/pk_bool`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_date`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_date32`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_datetime`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_datetime64`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_decimal`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_decimal_narrow`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_decimal_wide`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_int16`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_int32`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_int64`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_int8`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_interval`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_interval64`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_string`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_timestamp`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_timestamp64`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_uint16`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_uint32`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_uint64`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_uint8`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_utf8`) UNION ALL (
SELECT COUNT(*) FROM `replication/pk_uuid`) UNION ALL (
SELECT COUNT(*) FROM `replication/wide_json`) UNION ALL (
SELECT COUNT(*) FROM `replication/wide_json_doc`) UNION ALL (
SELECT COUNT(*) FROM `replication/wide_string`) UNION ALL (
SELECT COUNT(*) FROM `replication/wide_utf8`) UNION ALL (
SELECT COUNT(*) FROM `replication/wide_yson`
);
