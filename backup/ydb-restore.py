#! /usr/bin/env python3

import os
import logging
import argparse
import boto3

storage_client = None
boto_session = None
s3_endpoint = None

def getS3Client():
    global storage_client
    if storage_client is not None:
        return storage_client

    global boto_session
    if boto_session is None:
        access_key = os.getenv('AWS_ACCESS_KEY_ID')
        secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
        if access_key is None or secret_key is None:
            raise Exception("S3 secrets are missing")
        # initialize boto session
        boto_session = boto3.session.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )

    endpoint = os.getenv('S3_ENDPOINT')
    if endpoint is None:
        raise Exception("S3 endpoint is missing")
    storage_client = boto_session.client(
        service_name='s3',
        endpoint_url=endpoint,
    )
    global s3_endpoint
    s3_endpoint = endpoint
    return storage_client

def locateTables(bucket: str, prefix: str) -> dict:
    suffix = "/scheme.pb"
    if not prefix.endswith("/"):
        prefix = prefix + "/"
    if prefix.startswith("/"):
        prefix = prefix[1:]
    tablesDict = dict()
    logging.info(f"Scanning S3 bucket {bucket} at prefix {prefix} for table data...")
    prevToken = None
    while True:
        if prevToken is None:
            response = getS3Client().list_objects_v2(Bucket=bucket, Prefix=prefix)
        else:
            response = getS3Client().list_objects_v2(Bucket=bucket, Prefix=prefix, ContinuationToken=prevToken)
        contents = response.get('Contents', [])
        for item in contents:
            key = item.get('Key', None)
            if key is not None and key.endswith(suffix):
                datapath = key[:-len(suffix)]
                tabname = key[len(prefix):-len(suffix)]
                tablesDict[tabname] = datapath
                logging.info(f"... table `{tabname}` at {datapath}")
        isTruncated = response.get('IsTruncated', False)
        if not isTruncated:
            break
        prevToken = response.get('NextContinuationToken', None)
    return tablesDict

def buildBasicCommand(args: argparse.ArgumentParser) -> list:
    cmd = ['ydb']
    if args.profile is not None and len(args.profile) > 0:
        cmd.append('-p')
        cmd.append(args.profile)
    cmd.append('import')
    cmd.append('s3')
    cmd.append('--s3-endpoint')
    cmd.append(s3_endpoint)
    cmd.append('--bucket')
    cmd.append(args.bucket)
    return cmd

def buildCommands(cmdIn: list, dstprefix: str, maxtabs: int, tables: dict):
    if dstprefix is not None and len(dstprefix)>0 and dstprefix != '.':
        if not dstprefix.endswith("/"):
            dstprefix = dstprefix + "/"
        if dstprefix.startswith('/'):
            dstprefix = dstprefix[1:]
    hasPrefix = dstprefix is not None and len(dstprefix)>0 and dstprefix != '.'
    allCmds = []
    cmd = cmdIn.copy()
    for tabname, datapath in tables.items():
        tabpath = tabname
        if hasPrefix:
            tabpath = dstprefix + tabname
        cmd.append('--item')
        cmd.append('s=' + datapath + ',d=' + tabpath)
        if (len(cmd) - len(cmdIn)) / 2 >= maxtabs:
            allCmds.append(cmd)
            cmd = cmdIn.copy()
    if len(cmd) > len(cmdIn):
        allCmds.append(cmd)
    return allCmds

# S3_ENDPOINT=https://storage.yandexcloud.net python3 ydb-restore.py tpcc-backup0 /backup/test1 restore1
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('s3transfer').setLevel(logging.INFO)
    logging.getLogger('botocore').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)
    parser = argparse.ArgumentParser(description='YDB restore tool')
    parser.add_argument('bucket', type=str, help='S3 bucket name')
    parser.add_argument('inputPrefix', type=str, help='Backup storage input prefix')
    parser.add_argument('outputPrefix', type=str, help='YDB destination prefix')
    parser.add_argument('--tableLimit', type=int, default=50, help='Maximum tables per import command')
    parser.add_argument('--profile', type=str, help='YDB CLI connection profile name')
    args = parser.parse_args()
    tables = locateTables(args.bucket, args.inputPrefix)
    logging.info(f"Total {len(tables)} tables to be restored")
    cmdBase = buildBasicCommand(args)
    allCommands = buildCommands(cmdBase, args.outputPrefix, args.tableLimit, tables)
    for cmd in allCommands:
        print(cmd)
