# export YDB_ENDPOINT=grpc://ycydb-d1:2136
# export YDB_DATABASE=/Root/testdb
# export YDB_ACCESS_TOKEN_CREDENTIALS=`ydb -p stroppy auth get-token -f`
#
# export YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
# export YDB_DATABASE=/ru-central1/b1gfvslmokutuvt2g019/etnuogblap3e7dok6tf5
# export YDB_SERVICE_ACCOUNT_KEY_FILE_CREDENTIALS=/home/zinal/key_ydb-sa1.json
#
# python3 stroppy-account-builder.py 500

import os
import sys
import logging
import ydb

def countAccounts(pool: ydb.SessionPool) -> int:
    qtext = """
        SELECT COUNT(*) AS cnt FROM `stroppy/account`
    """
    def callee(session: ydb.Session) -> int:
        qp = session.prepare(qtext)
        rs = session.transaction().execute(qp, {})
        return rs[0].rows[0].cnt
    return pool.retry_operation_sync(callee)

def makeBorders(pool: ydb.SessionPool, partitionSize: int) -> list:
    qtext = """
        DECLARE $bic AS String; DECLARE $limit AS Int32;
        SELECT bic FROM `stroppy/account` WHERE bic > $bic ORDER BY bic LIMIT $limit;
    """
    prev_bic_str = ''
    cur_bic = prev_bic_str.encode('utf-8')
    cur_count = 0
    retval = []
    def callee(session: ydb.Session):
        nonlocal prev_bic_str, cur_bic, cur_count, retval
        qp = session.prepare(qtext)
        rs = session.transaction().execute(qp, {"$bic": cur_bic, "$limit": 500})
        if not rs[0].rows:
            return False
        for row in rs[0].rows:
            cur_bic = row.bic
            cur_count = cur_count + 1
            if cur_count >= partitionSize:
                cur_bic_str = cur_bic.decode('utf-8')
                if cur_bic_str != prev_bic_str:
                    prev_bic_str = cur_bic_str
                    retval.append(cur_bic_str)
                    cur_count = 0
        return True
    while True:
        if not pool.retry_operation_sync(callee):
            break
    return retval

def traceCounts(pool: ydb.SessionPool, borders: list):
    qtext = """
        DECLARE $bic1 AS String; DECLARE $bic2 AS String;
        SELECT COUNT(*) AS cnt FROM `stroppy/account` WHERE bic > $bic1 AND bic <= $bic2;
    """
    bic1 = ''
    bic2 = ''
    def callee(session: ydb.Session) -> int:
        nonlocal bic1, bic2
        qp = session.prepare(qtext)
        rs = session.transaction().execute(qp, {"$bic1": bic1.encode('utf-8'), "$bic2": bic2.encode('utf-8')})
        return rs[0].rows[0].cnt
    logging.info("Tracing partition statistics for total of {} partitions".format(len(borders)+1))
    for bic in borders:
        bic2 = bic
        cnt = pool.retry_operation_sync(callee)
        bic1 = bic
        logging.info("  partition {} -> {}".format(bic, cnt))
    bic2 = 'ZZZZZZZZ'
    cnt = pool.retry_operation_sync(callee)
    logging.info("  partition MAX -> {}".format(cnt))

def makeTableYql(borders: list, yqlFile: str):
    logging.info("Saving YQL for account2 table to {}".format(yqlFile))
    with open(yqlFile, "wt") as fout:
        fout.write("""
CREATE TABLE `stroppy/account2` (
  bic String,
  ban String,
  balance Int64,
  PRIMARY KEY(bic,ban)
) WITH (
  AUTO_PARTITIONING_BY_LOAD = ENABLED,
  AUTO_PARTITIONING_BY_SIZE = ENABLED,
  AUTO_PARTITIONING_MIN_PARTITIONS_COUNT = 1000,
  AUTO_PARTITIONING_MAX_PARTITIONS_COUNT = 1200,
  PARTITION_AT_KEYS = 
(\n""")
        needComma = False
        lineItems = 0
        for border in borders:
            lineItems = lineItems + 1
            if lineItems >= 10:
                fout.write("\n")
                lineItems = 0
            if needComma:
                fout.write(", '" + border + "'")
            else:
                fout.write("  '" + border + "'")
                needComma = True
        fout.write("\n));\n")

def makeShellScript(yqlFile: str, shellFile: str):
    logging.info("Saving shell commands to {}".format(shellFile))
    with open(shellFile, "wt") as fout:
        fout.write("#! /bin/sh\n")
        fout.write("set -e\n")
        fout.write("set -u\n")
        fout.write("# ydb config profile create stroppy\n")
        fout.write("ydb -p stroppy yql -f {}\n".format(yqlFile))
        fout.write("ydb -p stroppy table query exec -t scan -q 'SELECT * FROM `stroppy/account`' --format json-unicode \\\n")
        fout.write("   | ydb -p stroppy import file json -p stroppy/account2\n")
        fout.write("ydb -p stroppy tools rename --item src=stroppy/account,dst=stroppy/account_bak\n")
        fout.write("ydb -p stroppy tools rename --item src=stroppy/account2,dst=stroppy/account\n")

def readBordersImpl(driver: ydb.Driver, pool: ydb.SessionPool, num_partitions: int) -> list:
    accCount = countAccounts(pool)
    logging.info("Total number of accounts: {}".format(accCount))
    partitionSize = int(accCount / num_partitions) - 1
    if partitionSize < 1:
        partitionSize = 1
    logging.info("Partition size is {} for {} total partitions".format(partitionSize, num_partitions))
    borders = makeBorders(pool, partitionSize)
    traceCounts(pool, borders)
    return borders

def readBorders(ydb_endpoint: str, ydb_database: str, num_partitions: int):
    with ydb.Driver(endpoint=ydb_endpoint, database=ydb_database) as driver:
        driver.wait(timeout=5, fail_fast=True)
        with ydb.SessionPool(driver) as pool:
            return readBordersImpl(driver, pool, num_partitions)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('ydb').setLevel(logging.WARNING)
    num_partitions = 500
    if len(sys.argv) > 1:
        num_partitions = int(sys.argv[1])
    ydb_endpoint = os.getenv("YDB_ENDPOINT")
    if ydb_endpoint is None or len(ydb_endpoint)==0:
        raise Exception("missing YDB_ENDPOINT env")
    ydb_database = os.getenv("YDB_DATABASE")
    if ydb_database is None or len(ydb_database)==0:
        raise Exception("missing YDB_DATABASE env")
    borders = readBorders(ydb_endpoint, ydb_database, num_partitions)
    yqlFile = "stroppy-account.yql.tmp"
    shellFile = "stroppy-account.sh.tmp"
    makeTableYql(borders, yqlFile)
    makeShellScript(yqlFile, shellFile)
