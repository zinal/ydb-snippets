import os
import logging
import ydb

def run(pool: ydb.SessionPool, ydb_database: str):
    None

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
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
