CREATE TABLE `samples/request` (
   id Uint64 NOT NULL,
   int_ref Uint64 NOT NULL,
   tv Timestamp NOT NULL,
   event Text NOT NULL,
   sys_state Text NOT NULL,
   error_text Text,
   PRIMARY KEY(id),
   INDEX ix_ref GLOBAL ON (int_ref),
   INDEX ix_status GLOBAL ON (sys_state, error_text, event)
);

CREATE TABLE `samples/int_map` (
  id Uint64 NOT NULL,
  int_ref Uint64 NOT NULL,
  abonent Text,
  cancel_flag Bool,
  INDEX ix_ref GLOBAL ON (int_ref),
  PRIMARY KEY(id)
);

$main = (
    SELECT id, int_ref, tv FROM `samples/request` VIEW `ix_status`
    WHERE event IN ("GL_Rewrite", "GL_Delete", "Rewrite", "Order_Rewrite")
      AND sys_state = "PAUSED"
      AND error_text = "RDY"
);
$anti1 = (
    SELECT m.id AS id FROM $main AS m
    INNER JOIN `samples/request` VIEW `ix_ref` AS r
      ON r.int_ref=m.int_ref
    WHERE r.tv < m.tv
    AND (
        (r.sys_state="PAUSED" AND r.error_text="DRY")
        OR ( ( (r.sys_state IN ("NEW","SNT","RECEIVED","ACCEPTED") OR (r.sys_state="PAUSED" AND r.error_text="RDY")) AND
                r.event IN ("Rewrite", "Delete", "GL_Rewrite", "GL_Delete", "Order_Rewrite", "Order_Delete", "SendReceipt") )
            OR r.sys_state IN ("NEW", "SNT")
            OR (r.sys_state="PAUSED" AND r.error_text IN ("RDY", "WDE")) )
    )
);
$anti2 = (
    SELECT m.id AS id FROM $main AS m
    INNER JOIN `samples/int_map` VIEW `ix_ref` AS r
      ON r.int_ref=m.int_ref
    WHERE COALESCE(r.cancel_flag, false)=false
);
SELECT f.id AS id, f.tv AS tv FROM $main AS f
LEFT JOIN $anti1 AS r1 ON f.id=r1.id
LEFT JOIN $anti2 AS r2 ON f.id=r2.id
WHERE r1.id IS NULL AND r2.id IS NULL
ORDER BY tv;
