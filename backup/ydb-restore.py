#! /usr/bin/env python3

# This simple tool restores the full backup created by commands like
#   `ydb export s3 ... --item src=.,dst=backups/<backup_id>`
#
# Right now the `ydb import s3` command requires that each table
# has to be specified as a separate `--item` argument, which leads
# to the need to automate the process.
#
# The tool scans the specified S3 prefix for exported YDB tables,
# and generates the list of items to be imported. The import itself
# is initiated via the YDB API, and can be monitored through the
# regular `ydb operation list import/s3` commands.
#
# YDB connection options are read from the YDB CLI profile.
# This means that YDB CLI has to be installed on the same host
# where this tool runs, but that is logical as backups (export s3)
# operations require YDB CLI anyway.

import os
import yaml
import logging
import argparse
import boto3
from botocore.client import Config
import ydb
import ydb.iam

storage_client = None
boto_session = None
s3_endpoint = None
s3_key_id = None
s3_key_secret = None
ydb_database = None

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
        global s3_key_id, s3_key_secret
        s3_key_id = access_key
        s3_key_secret = secret_key

    endpoint = os.getenv('S3_ENDPOINT')
    if endpoint is None:
        raise Exception("S3 endpoint is missing")
    path_style = os.getenv('AWS_S3_PATH_STYLE') # path or virtual
    if path_style is None:
        logging.info(f"Implicit S3 path style for endpoint '{endpoint}'")
        storage_client = boto_session.client(
            service_name='s3',
            endpoint_url=endpoint,
        )
    else:
        logging.info(f"Explicit S3 path style '{path_style}' for endpoint '{endpoint}'")
        storage_client = boto_session.client(
            service_name='s3',
            endpoint_url=endpoint,
            config=Config(s3={'addressing_style': path_style}),
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
                logging.debug(f"... table `{tabname}` at {datapath}")
        isTruncated = response.get('IsTruncated', False)
        if not isTruncated:
            break
        prevToken = response.get('NextContinuationToken', None)
    logging.info(f"Total {len(tablesDict)} tables to be restored.")
    return tablesDict

def getYdbDriver(profile: str) -> ydb.Driver:
    allProfiles = []
    with open(os.getenv("HOME") + "/ydb/config/config.yaml") as stream:
        allProfiles = yaml.safe_load(stream)
    if profile is None:
        profile = allProfiles.get('active_profile')
    curProfile = allProfiles.get('profiles')
    if curProfile is not None:
        curProfile = curProfile.get(profile)
    if curProfile is None:
        raise Exception(f"Illegal YDB CLI profile: {profile}")
    caData = None
    caFile = curProfile.get('ca-file')
    if caFile is not None:
        with open(caFile, 'rb') as stream:
            caData = stream.read()
    credentials = ydb.AnonymousCredentials()
    authData = curProfile.get('authentication')
    if authData is not None:
        match authData.get('method'):
            case 'use-metadata-credentials':
                credentials = ydb.iam.MetadataUrlCredentials()
            case 'sa-key-file':
                credentials = ydb.iam.ServiceAccountCredentials.from_file(
                    key_file=authData.get('data'),
                )
            case 'static-credentials':
                loginInfo = authData.get('data')
                driverConfig = ydb.get_config(
                    endpoint=curProfile.get('endpoint'),
                    database=curProfile.get('database'),
                    root_certificates=caData,
                )
                credentials = ydb.StaticCredentials(
                    driver_config=driverConfig,
                    user=loginInfo.get('user'), 
                    password=loginInfo.get('password'),
                )
    global ydb_database
    ydb_database = curProfile.get('database')
    return ydb.Driver(
        endpoint=curProfile.get('endpoint'),
        database=ydb_database,
        credentials=credentials,
        root_certificates=caData,
    )

def importFromS3(driver: ydb.Driver, tables: dict, bucket: str, output_prefix: str):
    global ydb_database
    if output_prefix is not None and len(output_prefix)>0 and output_prefix != '.':
        if not output_prefix.endswith("/"):
            output_prefix = output_prefix + "/"
        if output_prefix.startswith('/'):
            output_prefix = output_prefix[1:]
    if output_prefix is None or len(output_prefix)==0 or output_prefix == '.':
        output_prefix = ydb_database
    else:
        output_prefix = ydb_database + "/" + output_prefix
    import_settings = (
        ydb.ImportFromS3Settings()
        .with_endpoint(s3_endpoint)
        .with_bucket(bucket)
        .with_access_key(s3_key_id)
        .with_secret_key(s3_key_secret)
    )
    for tabname, datapath in tables.items():
        tabpath = output_prefix + tabname
        import_settings.with_source_and_destination(datapath, tabpath)
        logging.debug(f"... configured {datapath} -> {tabpath}")
    import_client = ydb.ImportClient(driver)
    import_client.import_from_s3(import_settings)

# S3_ENDPOINT=https://storage.yandexcloud.net
# python3 ydb-restore.py tpcc-backup0 /backup/test1 restore1 --ydb_profile ydb0_tpcab
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('s3transfer').setLevel(logging.INFO)
    logging.getLogger('botocore').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.INFO)
    logging.getLogger('ydb').setLevel(logging.WARN)
    parser = argparse.ArgumentParser(description='YDB restore tool')
    parser.add_argument('bucket', type=str, help='S3 bucket name')
    parser.add_argument('input_prefix', type=str, help='Backup storage input prefix')
    parser.add_argument('output_prefix', type=str, help='YDB destination prefix, "." for database root')
    parser.add_argument('--ydb_profile', type=str, help='YDB CLI connection profile name')
    args = parser.parse_args()
    with getYdbDriver(args.ydb_profile) as driver:
        driver.wait(timeout=10)
        tables = locateTables(args.bucket, args.input_prefix)
        importFromS3(driver, tables, args.bucket, args.output_prefix)
