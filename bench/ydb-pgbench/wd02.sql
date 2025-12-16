SELECT a.aid, a.abalance,  
       b.bbalance,   -- Corrected column name (from bname)
       t.tbalance    -- Corrected column name (from tname)
FROM `{table_folder}/accounts` a
JOIN `{table_folder}/branches` b ON a.bid = b.bid  -- JOIN 1: Accounts links to Branches on BID
JOIN `{table_folder}/tellers` view `teller_branch` t ON b.bid = t.bid   -- JOIN 2: Tellers links to Branches on BID
;