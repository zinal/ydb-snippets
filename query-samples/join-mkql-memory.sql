DROP TABLE `mkql-mem/bank_document`;
DROP TABLE `mkql-mem/bank_sub_document`;

CREATE TABLE `mkql-mem/bank_document` (
    id                       Text NOT NULL,
    message_type_id          Text,
    bank_direction           Text,
    amount                   Decimal(22,9),
    amount_kt                Decimal(22,9),
    amount_nt                Decimal(22,9),
    cur                      Text,
    cur_kt                   Text,
    creation_dt              Timestamp,
    dt                       Timestamp,
    value_dt                 Timestamp,
    exec_dt                  Timestamp,
    receive_dt               Timestamp,
    send_received_dttm       Timestamp,
    uetr                     Text,
    rejected                 Bool,
    error_code               Text,
    error_text               Text,
    reference                Text,
    related_reference        Text,
    in_file_name             Text,
    format                   Text,
    multiformat_flag         Bool,
    kl_dt_type               Int32,
    kl_dt_client_id          Text,
    kl_dt_acc_id             Text,
    kl_dt_bank_id            Text,
    kl_dt_client_name        Text,
    kl_dt_acc_num            Text,
    kl_dt_client_inn         Text,
    kl_dt_client_kpp         Text,
    kl_kt_type               Int32,
    kl_kt_client_id          Text,
    kl_kt_acc_id             Text,
    kl_kt_bank_id            Text,
    kl_kt_client_name        Text,
    kl_kt_acc_num            Text,
    kl_kt_client_inn         Text,
    kl_kt_client_kpp         Text,
    acc_dt_id                Text,
    product_dt_ref           Text,
    product_dt_ref_sys_class Text,
    acc_kt_id                Text,
    product_kt_ref           Text,
    product_kt_ref_sys_class Text,
    buh_state                Text,
    sys_state                Text,
    num                      Text,
    kind_id                  Text,
    type_send_id             Text,
    purpose                  Text,
    purpose_code_id          Text,
    priority                 Int32,
    payment_ident            Text,
    header                   Text,
    grp                      Text,
    text                     Text,
    original_doc             String,
    prov_user_id             Text,
    document_user_id         Text,
    attributes               String,
    depart_id                Text,
    branch_id                Text,
    internal_code            Text,
    auto_proc                Bool,
    sub_documents            Text,
    checkup_package_item_id  Text,
    sys_crt_dttm             Timestamp,
    sys_crt_user             Text,
    sys_import               Bool,
    sys_sn                   Int64,
    sys_upd_dttm             Timestamp,
    sys_upd_user             Text,
    sys_audit_flags          Text,
    stage                    Text,
    src_type                 Text,
    src_part                 Text,
    dst_part                 Text,
    src_contract_id          Text,
    dst_contract_id          Text,
    src_bank_code            Text,
    dst_bank_code            Text,
    dst_type                 Text,
    src_channel_id           Text,
    dst_channel_id           Text,
    src_ident                Text,
    dst_ident                Text,
    PRIMARY KEY(id),
    INDEX IX_BANK_DOCUMENT_KL_DT_ACC_ID            GLOBAL ON (kl_dt_acc_id),
    INDEX IX_BANK_DOCUMENT_KL_DT_BANK_ID           GLOBAL ON (kl_dt_bank_id),
    INDEX IX_BANK_DOCUMENT_KL_DT_CLIENT_ID         GLOBAL ON (kl_dt_client_id),
    INDEX IX_BANK_DOCUMENT_KL_KT_ACC_ID            GLOBAL ON (kl_kt_acc_id),
    INDEX IX_BANK_DOCUMENT_KL_KT_BANK_ID           GLOBAL ON (kl_kt_bank_id),
    INDEX IX_BANK_DOCUMENT_KL_KT_CLIENT_ID         GLOBAL ON (kl_kt_client_id),
    INDEX ix_bank_document_checkup_package_item_id GLOBAL ON (checkup_package_item_id),
    INDEX ix_bank_document_dt                      GLOBAL ON (dt),
    INDEX ix_bank_document_exec_dt                 GLOBAL ON (exec_dt,acc_dt_id,acc_kt_id) COVER(sys_state,buh_state),
    INDEX ix_bank_document_src_ident               GLOBAL ON (src_ident),
    INDEX ix_bank_document_dst_ident               GLOBAL ON (dst_ident),
    INDEX ix_bank_document_sub_documents           GLOBAL ON (sub_documents)
) WITH (
    AUTO_PARTITIONING_BY_LOAD = ENABLED,
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 1000,
    AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 1000,
    PARTITION_AT_KEYS = (
"-4","-A","-F","-L","-R","-X","-d","-j","-p","-v","0-","04","0A","0F","0L","0R","0X","0d","0j","0p","0v","1-","14","1A","1F","1L","1R","1X","1d","1j","1p","1v","2-","24","2A","2F","2L","2R","2X","2d",
"2j","2p","2v","3-","34","3A","3F","3L","3R","3X","3d","3j","3p","3v","4-","44","4A","4F","4L","4R","4X","4d","4j","4p","4v","5-","54","5A","5F","5L","5R","5X","5d","5j","5p","5v","6-","64","6A","6F",
"6L","6R","6X","6d","6j","6p","6v","7-","74","7A","7F","7L","7R","7X","7d","7j","7p","7v","8-","84","8A","8F","8L","8R","8X","8d","8j","8p","8v","9-","94","9A","9F","9L","9R","9X","9d","9j","9p","9v",
"A-","A4","AA","AF","AL","AR","AX","Ad","Aj","Ap","Av","B-","B4","BA","BF","BL","BR","BX","Bd","Bj","Bp","Bv","C-","C4","CA","CF","CL","CR","CX","Cd","Cj","Cp","Cv","D-","D4","DA","DF","DL","DR","DX",
"Dd","Dj","Dp","Dv","E-","E4","EA","EF","EL","ER","EX","Ed","Ej","Ep","Ev","F-","F4","FA","FF","FL","FR","FX","Fd","Fj","Fp","Fv","G-","G4","GA","GF","GL","GR","GX","Gd","Gj","Gp","Gv","H-","H4","HA",
"HF","HL","HR","HX","Hd","Hj","Hp","Hv","I-","I4","IA","IF","IL","IR","IX","Id","Ij","Ip","Iv","J-","J4","JA","JF","JL","JR","JX","Jd","Jj","Jp","Jv","K-","K4","KA","KF","KL","KR","KX","Kd","Kj","Kp",
"Kv","L-","L4","LA","LF","LL","LR","LX","Ld","Lj","Lp","Lv","M-","M4","MA","MF","ML","MR","MX","Md","Mj","Mp","Mv","N-","N4","NA","NF","NL","NR","NX","Nd","Nj","Np","Nv","O-","O4","OA","OF","OL","OR",
"OX","Od","Oj","Op","Ov","P-","P4","PA","PF","PL","PR","PX","Pd","Pj","Pp","Pv","Q-","Q4","QA","QF","QL","QR","QX","Qd","Qj","Qp","Qv","R-","R4","RA","RF","RL","RR","RX","Rd","Rj","Rp","Rv","S-","S4",
"SA","SF","SL","SR","SX","Sd","Sj","Sp","Sv","T-","T4","TA","TF","TL","TR","TX","Td","Tj","Tp","Tv","U-","U4","UA","UF","UL","UR","UX","Ud","Uj","Up","Uv","V-","V4","VA","VF","VL","VR","VX","Vd","Vj",
"Vp","Vv","W-","W4","WA","WF","WL","WR","WX","Wd","Wj","Wp","Wv","X-","X4","XA","XF","XL","XR","XX","Xd","Xj","Xp","Xv","Y-","Y4","YA","YF","YL","YR","YX","Yd","Yj","Yp","Yv","Z-","Z4","ZA","ZF","ZL",
"ZR","ZX","Zd","Zj","Zp","Zv","_-","_4","_A","_F","_L","_R","_X","_d","_j","_p","_v","a-","a4","aA","aF","aL","aR","aX","ad","aj","ap","av","b-","b4","bA","bF","bL","bR","bX","bd","bj","bp","bv","c-",
"c4","cA","cF","cL","cR","cX","cd","cj","cp","cv","d-","d4","dA","dF","dL","dR","dX","dd","dj","dp","dv","e-","e4","eA","eF","eL","eR","eX","ed","ej","ep","ev","f-","f4","fA","fF","fL","fR","fX","fd",
"fj","fp","fv","g-","g4","gA","gF","gL","gR","gX","gd","gj","gp","gv","h-","h4","hA","hF","hL","hR","hX","hd","hj","hp","hv","i-","i4","iA","iF","iL","iR","iX","id","ij","ip","iv","j-","j4","jA","jF",
"jL","jR","jX","jd","jj","jp","jv","k-","k4","kA","kF","kL","kR","kX","kd","kj","kp","kv","l-","l4","lA","lF","lL","lR","lX","ld","lj","lp","lv","m-","m4","mA","mF","mL","mR","mX","md","mj","mp","mv",
"n-","n4","nA","nF","nL","nR","nX","nd","nj","np","nv","o-","o4","oA","oF","oL","oR","oX","od","oj","op","ov","p-","p4","pA","pF","pL","pR","pX","pd","pj","pp","pv","q-","q4","qA","qF","qL","qR","qX",
"qd","qj","qp","qv","r-","r4","rA","rF","rL","rR","rX","rd","rj","rp","rv","s-","s4","sA","sF","sL","sR","sX","sd","sj","sp","sv","t-","t4","tA","tF","tL","tR","tX","td","tj","tp","tv","u-","u4","uA",
"uF","uL","uR","uX","ud","uj","up","uv","v-","v4","vA","vF","vL","vR","vX","vd","vj","vp","vv","w-","w4","wA","wF","wL","wR","wX","wd","wj","wp","wv","x-","x4","xA","xF","xL","xR","xX","xd","xj","xp",
"xv","y-","y4","yA","yF","yL","yR","yX","yd","yj","yp","yv","z-","z4","zA","zF","zL","zR","zX","zd","zj","zp","zv"
    )
);

CREATE TABLE `mkql-mem/bank_sub_document` (
    document_id     Text,
    collection_id   Text,
    link_type_id    Text,
    sys_crt_dttm    Timestamp,
    sys_crt_user    Text,
    sys_import      Bool,
    sys_sn          Int64,
    sys_upd_dttm    Timestamp,
    sys_upd_user    Text,
    sys_audit_flags Text,
    PRIMARY KEY (document_id, collection_id),
    INDEX IX_BANK_SUB_DOCUMENT_COLLECTION_ID GLOBAL ON (collection_id)
) WITH (
    AUTO_PARTITIONING_BY_LOAD = ENABLED,
    AUTO_PARTITIONING_BY_SIZE = ENABLED,
    AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 500,
    AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 500,
    PARTITION_AT_KEYS = (
"-4","-A","-F","-L","-R","-X","-d","-j","-p","-v","0-","04","0A","0F","0L","0R","0X","0d","0j","0p","0v","1-","14","1A","1F","1L","1R","1X","1d","1j","1p","1v","2-","24","2A","2F","2L","2R","2X","2d",
"2j","2p","2v","3-","34","3A","3F","3L","3R","3X","3d","3j","3p","3v","4-","44","4A","4F","4L","4R","4X","4d","4j","4p","4v","5-","54","5A","5F","5L","5R","5X","5d","5j","5p","5v","6-","64","6A","6F",
"6L","6R","6X","6d","6j","6p","6v","7-","74","7A","7F","7L","7R","7X","7d","7j","7p","7v","8-","84","8A","8F","8L","8R","8X","8d","8j","8p","8v","9-","94","9A","9F","9L","9R","9X","9d","9j","9p","9v",
"A-","A4","AA","AF","AL","AR","AX","Ad","Aj","Ap","Av","B-","B4","BA","BF","BL","BR","BX","Bd","Bj","Bp","Bv","C-","C4","CA","CF","CL","CR","CX","Cd","Cj","Cp","Cv","D-","D4","DA","DF","DL","DR","DX",
"Dd","Dj","Dp","Dv","E-","E4","EA","EF","EL","ER","EX","Ed","Ej","Ep","Ev","F-","F4","FA","FF","FL","FR","FX","Fd","Fj","Fp","Fv","G-","G4","GA","GF","GL","GR","GX","Gd","Gj","Gp","Gv","H-","H4","HA",
"HF","HL","HR","HX","Hd","Hj","Hp","Hv","I-","I4","IA","IF","IL","IR","IX","Id","Ij","Ip","Iv","J-","J4","JA","JF","JL","JR","JX","Jd","Jj","Jp","Jv","K-","K4","KA","KF","KL","KR","KX","Kd","Kj","Kp",
"Kv","L-","L4","LA","LF","LL","LR","LX","Ld","Lj","Lp","Lv","M-","M4","MA","MF","ML","MR","MX","Md","Mj","Mp","Mv","N-","N4","NA","NF","NL","NR","NX","Nd","Nj","Np","Nv","O-","O4","OA","OF","OL","OR",
"OX","Od","Oj","Op","Ov","P-","P4","PA","PF","PL","PR","PX","Pd","Pj","Pp","Pv","Q-","Q4","QA","QF","QL","QR","QX","Qd","Qj","Qp","Qv","R-","R4","RA","RF","RL","RR","RX","Rd","Rj","Rp","Rv","S-","S4",
"SA","SF","SL","SR","SX","Sd","Sj","Sp","Sv","T-","T4","TA","TF","TL","TR","TX","Td","Tj","Tp","Tv","U-","U4","UA","UF","UL","UR","UX","Ud","Uj","Up","Uv","V-","V4","VA","VF","VL","VR","VX","Vd","Vj",
"Vp","Vv","W-","W4","WA","WF","WL","WR","WX","Wd","Wj","Wp","Wv","X-","X4","XA","XF","XL","XR","XX","Xd","Xj","Xp","Xv","Y-","Y4","YA","YF","YL","YR","YX","Yd","Yj","Yp","Yv","Z-","Z4","ZA","ZF","ZL",
"ZR","ZX","Zd","Zj","Zp","Zv","_-","_4","_A","_F","_L","_R","_X","_d","_j","_p","_v","a-","a4","aA","aF","aL","aR","aX","ad","aj","ap","av","b-","b4","bA","bF","bL","bR","bX","bd","bj","bp","bv","c-",
"c4","cA","cF","cL","cR","cX","cd","cj","cp","cv","d-","d4","dA","dF","dL","dR","dX","dd","dj","dp","dv","e-","e4","eA","eF","eL","eR","eX","ed","ej","ep","ev","f-","f4","fA","fF","fL","fR","fX","fd",
"fj","fp","fv","g-","g4","gA","gF","gL","gR","gX","gd","gj","gp","gv","h-","h4","hA","hF","hL","hR","hX","hd","hj","hp","hv","i-","i4","iA","iF","iL","iR","iX","id","ij","ip","iv","j-","j4","jA","jF",
"jL","jR","jX","jd","jj","jp","jv","k-","k4","kA","kF","kL","kR","kX","kd","kj","kp","kv","l-","l4","lA","lF","lL","lR","lX","ld","lj","lp","lv","m-","m4","mA","mF","mL","mR","mX","md","mj","mp","mv",
"n-","n4","nA","nF","nL","nR","nX","nd","nj","np","nv","o-","o4","oA","oF","oL","oR","oX","od","oj","op","ov","p-","p4","pA","pF","pL","pR","pX","pd","pj","pp","pv","q-","q4","qA","qF","qL","qR","qX",
"qd","qj","qp","qv","r-","r4","rA","rF","rL","rR","rX","rd","rj","rp","rv","s-","s4","sA","sF","sL","sR","sX","sd","sj","sp","sv","t-","t4","tA","tF","tL","tR","tX","td","tj","tp","tv","u-","u4","uA",
"uF","uL","uR","uX","ud","uj","up","uv","v-","v4","vA","vF","vL","vR","vX","vd","vj","vp","vv","w-","w4","wA","wF","wL","wR","wX","wd","wj","wp","wv","x-","x4","xA","xF","xL","xR","xX","xd","xj","xp",
"xv","y-","y4","yA","yF","yL","yR","yX","yd","yj","yp","yv","z-","z4","zA","zF","zL","zR","zX","zd","zj","zp","zv"
    )
);


UPSERT INTO `mkql-mem/bank_document`
  SELECT * FROM bank_document
  WHERE exec_dt BETWEEN DateTime('2024-10-01T00:00:00Z') AND DateTime('2024-11-01T00:00:00Z')
  ORDER BY exec_dt ASC
  LIMIT 1000;

UPSERT INTO `mkql-mem/bank_sub_document`
  SELECT * FROM bank_sub_document
  WHERE document_id IN (SELECT id FROM `mkql-mem/bank_document`);

UPSERT INTO `mkql-mem/bank_document`
  SELECT * FROM bank_document view ix_bank_document_sub_documents
  WHERE sub_documents IN (SELECT collection_id FROM `mkql-mem/bank_sub_document`);

SELECT * FROM (
    SELECT id, COUNT(*) AS cnt FROM (
        SELECT doc.*, svod_doc.id AS svdoc_id
        FROM `mkql-mem/bank_document` AS doc 
        CROSS JOIN ( SELECT id FROM sys_enum_item VIEW ix_sys_enum_item_code_sys_class WHERE sys_class = 'BANK_LINK_TYPE'u AND code = 'СВОД' ) AS sc 
        LEFT JOIN `mkql-mem/bank_sub_document` sub_doc
            ON sub_doc . document_id = doc . id AND sub_doc . link_type_id = sc . id 
        LEFT JOIN `mkql-mem/bank_document` VIEW ix_bank_document_sub_documents AS svod_doc
            ON svod_doc . sub_documents = sub_doc . collection_id
    )
    WHERE exec_dt BETWEEN Timestamp("2024-10-06T00:00:00.000000Z") AND Timestamp("2024-10-07T00:00:00.000000Z")
    GROUP BY id
) ORDER BY cnt DESC LIMIT 10;

SELECT * FROM (
    SELECT id, COUNT(*) AS cnt FROM (
        SELECT doc.*, svod_doc.id AS svdoc_id
        FROM `mkql-mem/bank_document` AS doc 
        LEFT JOIN (
            SELECT * FROM `mkql-mem/bank_sub_document`
            WHERE link_type_id = "TIYPrl3gQ1uE_argyh4i7g"u
        ) AS sub_doc
            ON sub_doc . document_id = doc . id
        LEFT JOIN `mkql-mem/bank_document` VIEW ix_bank_document_sub_documents AS svod_doc
            ON svod_doc . sub_documents = sub_doc . collection_id
    )
    WHERE exec_dt BETWEEN Timestamp("2024-10-06T00:00:00.000000Z") AND Timestamp("2024-10-07T00:00:00.000000Z")
    GROUP BY id
) ORDER BY cnt DESC LIMIT 10;
