UPDATE `{table_folder}/accounts` SET abalance = abalance + $delta WHERE aid = $aid;
SELECT abalance FROM `{table_folder}/accounts` WHERE aid = $aid;
UPDATE `{table_folder}/tellers` SET tbalance = tbalance + $delta WHERE tid = $tid;
UPDATE `{table_folder}/branches` SET bbalance = bbalance + $delta WHERE bid = $bid;
INSERT INTO `{table_folder}/history` (tid, bid, aid, delta, mtime)
VALUES ($tid, $bid, $aid, $delta, CurrentUtcTimestamp());
