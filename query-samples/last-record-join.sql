CREATE TABLE bank_document (
  id Text NOT NULL,
  exec_date Date,
  PRIMARY KEY(id)
);

CREATE TABLE int_out_request (
  id Text NOT NULL,
  int_ref Text,
  send_dttm Timestamp,
  sys_state Text,
  abonent Text,
  INDEX ix_ref GLOBAL ON (int_ref) COVER(send_dttm, sys_state, abonent),
  PRIMARY KEY(id)
);


CREATE VIEW `/Domain0/testdb/demo1` WITH (security_invoker = TRUE) AS
SELECT ior.int_ref AS doc_id, MIN(ior.id) AS ior_id
FROM (SELECT int_ref, MAX(send_dttm) AS max_send_dttm
      FROM `/Domain0/testdb/int_out_request`
      WHERE sys_state = "SENT" AND abonent = "CBR"
      GROUP BY int_ref) AS ior_max
INNER JOIN `/Domain0/testdb/int_out_request` ior
        ON ior.int_ref = ior_max.int_ref
       AND ior.send_dttm = ior_max.max_send_dttm
GROUP BY ior.int_ref;


SELECT bank_document.id, int_out_request_join.id AS int_out_request_id,
FROM `/local/bank_document` AS bank_document
         LEFT JOIN `/local/int_out_request` AS int_out_request_join ON int_out_request_join.int_ref = bank_document.id
    and int_out_request_join.send_dttm = (select CAST(MAX(inner_out.send_dttm) AS TIMESTAMP)
                                          from `/local/int_out_request` as inner_out
                                          where inner_out.int_ref = bank_document.id
                                            and inner_out.sys_state = 'SENT'
                                            and inner_out.abonent = 'CBR')
group by bank_document.id,
         int_out_request_join.id;


SELECT distinct bank_document.id              as bank_document_id,
                int_out_request.out_packet_id as out_packet_id,
                int_out_request.id            AS int_out_request_id,
                int_out_request.int_ref       as int_ref,
                int_out_request.sddt
FROM `/local/bank_document` AS bank_document
         LEFT JOIN (select inner_out.send_dttm as sddt,
                           inner_out.id,
                           inner_out.int_ref,
                           inner_out.abonent,
                           inner_out.sys_state,
                           inner_out.out_packet_id,
                    from `/local/int_out_request` as inner_out
                    where inner_out.sys_state = 'SENT'
                      and inner_out.abonent = 'CBR'
                      and inner_out.int_ref is not null
                      and inner_out.send_dttm is not null
                    order by sddt desc) as int_out_request
                   on int_out_request.int_ref = bank_document.id
where bank_document.id = '-03UT6etTHuEGeVTSm6Y9w';
