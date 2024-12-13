CREATE VIEW bank_document_view WITH (security_invoker = TRUE) AS
SELECT doc.*,
    JSON_VALUE(cast(doc.attributes AS Json), '$.flags.arrayNum' RETURNING integer) AS flags_array_num,
    sum.num                                                                        AS summary_num
FROM bank_document AS doc
LEFT JOIN (
    SELECT d.num AS num, s.document_id AS single_doc_id
    FROM bank_document d
                INNER JOIN bank_sub_document s ON s.collection_id = d.sub_documents
    WHERE s.link_type_id IN
            (SELECT e.id
            FROM sys_enum_item e
            WHERE e.sys_class = 'BANK_LINK_TYPE'
                AND e.code = 'СВОД')) AS sum
ON sum.single_doc_id = doc.id;


alter table bank_document add index ix_bank_document_sub_documents global on (sub_documents);
alter table bank_document add index ix_bank_document_dt global on (dt);

CREATE VIEW bank_document_view WITH (security_invoker = TRUE) AS
SELECT
    doc1.*, 
    JSON_VALUE(cast(doc1.attributes AS Json), '$.flags.arrayNum' RETURNING integer) AS flags_array_num,
    doc2.num AS summary_num
FROM bank_document AS doc1
LEFT JOIN bank_sub_document VIEW IX_BANK_SUB_DOCUMENT_DOCUMENT_ID AS subdoc
    ON subdoc.document_id = doc1.id
LEFT JOIN bank_document VIEW ix_bank_document_sub_documents AS doc2
    ON subdoc.collection_id = doc2.sub_documents
WHERE doc2.id IS NULL OR subdoc.link_type_id IN (
    SELECT id FROM sys_enum_item WHERE sys_class='BANK_LINK_TYPE'u  AND code = 'СВОД'u
);

SELECT * FROM bank_document_view WHERE dt=Timestamp("2024-08-23T00:00:00.000000Z") ORDER BY dt, id LIMIT 50;

SELECT * FROM bank_document WHERE dt=Timestamp("2024-08-23T00:00:00.000000Z") ORDER BY dt, id LIMIT 50;