import os
import logging
import ydb

def run(pool, ydb_database):
    def callee(session: ydb.Session):
        qtext = """
            SELECT 123 AS cnt;
        """
        qp = session.prepare(qtext)
        rs = session.transaction().execute(qp)
        if (rs is None or len(rs)==0 or rs[0].rows is None or len(rs[0].rows)==0):
            xval = -1
        else:
            xval = rs[0].rows[0].cnt
        if xval is None:
            xval = -1
        logging.info("Counter returned {}".format(xval))
    return pool.retry_operation_sync(callee)


# export YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
# export YDB_DATABASE=/ru-central1/b1g1hfek2luako6vouqb/etno6m1l1lf4ae3j01ej
# export YDB_SERVICE_ACCOUNT_KEY_FILE_CREDENTIALS=keys/dp-compute-colorizer.json
# python3 helloworld.py
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    logging.getLogger('ydb').setLevel(logging.WARNING)
    ydb_endpoint = os.getenv("YDB_ENDPOINT")
    if ydb_endpoint is None or len(ydb_endpoint)==0:
        raise Exception("missing YDB_ENDPOINT env")
    ydb_database = os.getenv("YDB_DATABASE")
    if ydb_database is None or len(ydb_database)==0:
        raise Exception("missing YDB_DATABASE env")
    with ydb.Driver(endpoint=ydb_endpoint, database=ydb_database) as driver:
        driver.wait(timeout=5, fail_fast=True)
        with ydb.SessionPool(driver) as pool:
            run(pool, ydb_database)
