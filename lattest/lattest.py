import os
import sys
import random
import importlib.metadata
from timeit import default_timer as timer
import logging
import ydb

def ydbConnect() -> ydb.Driver:
    ydb_endpoint = os.getenv("YDB_ENDPOINT")
    if ydb_endpoint is None or len(ydb_endpoint)==0:
        raise Exception("missing YDB_ENDPOINT env")
    ydb_database = os.getenv("YDB_DATABASE")
    if ydb_database is None or len(ydb_database)==0:
        raise Exception("missing YDB_DATABASE env")
    ydb_username = os.getenv("YDB_USER")
    ydb_password = os.getenv("YDB_PASSWORD")
    rootCerts = ydb.load_ydb_root_certificate()
    driverConfig = ydb.get_config(endpoint=ydb_endpoint, 
                                  database=ydb_database,
                                  root_certificates=rootCerts)
    creds = ydb.credentials_from_env_variables()
    if ydb_username is not None and len(ydb_username) > 0:
        creds = ydb.StaticCredentials(driverConfig, user=ydb_username, password=ydb_password)
    connStart = timer()
    driver = ydb.Driver(endpoint=ydb_endpoint,
                    database=ydb_database,
                    root_certificates=rootCerts,
                    credentials=creds)
    driver.wait(timeout=5, fail_fast=True)
    return driver

ydb_driver = ydbConnect()
ydb_pool = ydb.SessionPool(ydb_driver)

def runStep(pool: ydb.SessionPool, operCur: int):
    query = """
DECLARE $p AS Int32; SELECT 1+$p AS out;
    """
    def callee(session: ydb.Session):
        qp = session.prepare(query)
        txc = session.transaction(ydb.SerializableReadWrite())
        for i in range(operCur):
            input = random.randrange(1, 10000)
            rs = txc.execute(qp, {"$p": input})
            output = rs[0].rows[0].out
            if input+1 != output:
                raise Exception("illegal output: expected " + str(input+1) + ", actual " + str(output))
    pool.retry_operation_sync(callee, ydb.RetrySettings(idempotent=True))
    None

def runCtx(pool: ydb.SessionPool, operTotal: int):
    operDone = 0
    while operDone < operTotal:
        operCur = random.randrange(3, 10)
        if operDone + operCur > operTotal:
            operCur = operTotal - operDone
        runStep(pool, operCur)
        operDone = operDone + operCur

def run(operTotal: int):
    operStart = timer()
    runCtx(ydb_pool, operTotal)
    operFinish = timer()
    operTime = (operFinish - operStart)
    operAvg = 1000 * (operTime / operTotal)
    print("'xstat', " + str(operTotal) + ", " + str(operTime) + ", " + str(operAvg))

# Cloud Function entry point
def handler(event, context):
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger('ydb').setLevel(logging.WARNING)
    run(100)

# Self-contained entry point
if __name__ == '__main__':
    print("YDB Python SDK version " + importlib.metadata.version("ydb"))
    operTotal = 1000
    if len(sys.argv) > 1:
        operTotal = int(sys.argv[1])
    run(operTotal)

