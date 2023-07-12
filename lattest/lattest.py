import os
import sys
import random
import importlib.metadata
import ydb

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
            print("Connected!")
            runCtx(pool, operTotal)

if __name__ == '__main__':
    print("YDB Python SDK version " + importlib.metadata.version("ydb"))
    operTotal = 1000
    if len(sys.argv) > 1:
        operTotal = int(sys.argv[1])
    run(operTotal)

