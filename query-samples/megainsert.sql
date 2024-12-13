
alter table bank_document add index ix_bank_document_exec_dt_accounts 
  global on (exec_dt, acc_dt_id, acc_kt_id) cover(buh_state, sys_state);

DECLARE $dateFrom AS Timestamp;
DECLARE $dateTo AS Timestamp;
DECLARE $accDtId AS Text;
DECLARE $accKtId AS Text;
DECLARE $buhState AS Text;
DECLARE $sysStates AS List<Text>;
DECLARE $collectionId AS Text;
DECLARE $linkTypeId AS Text;

INSERT INTO bank_sub_document
SELECT
    Unwrap(CAST(Substring(String::Base64Encode(ToBytes(RandomUuid(doc.id))),0,22) AS Text)) AS id,
    doc.document_id AS document_id,
    $collectionId AS collection_id,
    $linkTypeId AS link_type_id,
    1 AS sys_sn
FROM (
SELECT d.id AS document_id, d.exec_dt AS exec_dt
FROM bank_document VIEW ix_bank_document_exec_dt_accounts AS d
LEFT JOIN bank_sub_document VIEW IX_BANK_SUB_DOCUMENT_DOCUMENT_ID AS sd
  ON d.id = sd.document_id
WHERE sd.document_id IS NULL
  AND d.exec_dt >= $dateFrom
  AND d.exec_dt < $dateTo
  AND d.acc_dt_id = $accDtId
  AND d.acc_kt_id = $accKtId
  AND d.buh_state = $buhState
  AND d.sys_state IN $sysStates
ORDER BY exec_dt, document_id
LIMIT 10000
) AS doc;

SELECT * FROM (
SELECT exec_dt, acc_dt_id, acc_kt_id, buh_state, sys_state, COUNT(*) AS cnt
FROM bank_document WHERE exec_dt IS NOT NULL
GROUP BY exec_dt, acc_dt_id, acc_kt_id, buh_state, sys_state
) ORDER BY cnt DESC LIMIT 1;

$dateFrom=Timestamp("2024-09-18T21:00:00.000000Z");
$dateTo=Timestamp("2024-09-19T21:00:00.000000Z");
$accDtId = "GfNJaLeWRnegJ2vg4emIjA"u;
$accKtId = "4nnp8bleTo-6Cm18cGTqhA"u;
$buhState = "PROV"u;
$sysStates = [ "S_99"u ];
$collectionId = "aaa"u;
$linkTypeId = "bbb"u;
