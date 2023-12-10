import os
import logging
import random
import ydb

def run(pool: ydb.SessionPool, ydb_database: str):
    STR_KEYS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
                "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T",
                "U", "V", "W", "X", "Y", "Z"]
    query = """
DECLARE $v AS List<Struct<a:Int32, b:Text>>;
UPSERT INTO `async-index-demo` SELECT * FROM AS_TABLE($v);
"""
    values = []
    def callee(session: ydb.Session):
        qp = session.prepare(query)
        session.transaction(ydb.SerializableReadWrite()).execute(
            qp, {"$v": values}, commit_tx=True,
        )
    while True:
        for i in range(100):
            values.append({"a": random.randint(0, 99999), "b": random.choice(STR_KEYS)})
        pool.retry_operation_sync(callee)
        values.clear()

# export YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
# export YDB_DATABASE=/ru-central1/b1gfvslmokutuvt2g019/etnuogblap3e7dok6tf5
# export YDB_SERVICE_ACCOUNT_KEY_FILE_CREDENTIALS=/home/zinal/Keys/ydb-sa1-key1.json
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('ydb').setLevel(logging.WARNING)
    ydb_endpoint = os.getenv("YDB_ENDPOINT")
    if ydb_endpoint is None or len(ydb_endpoint)==0:
        raise Exception("missing YDB_ENDPOINT env")
    ydb_database = os.getenv("YDB_DATABASE")
    if ydb_database is None or len(ydb_database)==0:
        raise Exception("missing YDB_DATABASE env")
    with ydb.Driver(endpoint=ydb_endpoint,
                    database=ydb_database,
                    credentials=ydb.credentials_from_env_variables()) as driver:
        driver.wait(timeout=5, fail_fast=True)
        with ydb.SessionPool(driver) as pool:
            run(pool, ydb_database)
