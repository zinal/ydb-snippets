#! /usr/bin/env python3

from __future__ import annotations

# Правит scheme.pb в выгрузке YDB на S3, чтобы документные таблицы
# импортировались как обычные.
#
# Выгрузка YDB хранит схему таблицы в текстовом protobuf (scheme.pb).
# Документная таблица отмечена атрибутом __document_api_version, а описание
# индексов Document API лежит в атрибутах с префиксом dynamodb. Пока эти
# атрибуты на месте, импорт считает таблицу документной. Скрипт удаляет
# только их и оставляет остальной текст схемы байт в байт: так импорт
# получает ту же схему без признаков Document API.
#
# Рядом с scheme.pb YDB кладёт scheme.pb.sha256 (формат sha256sum).
# Импорт сверяет контрольную сумму с телом объекта, поэтому после правки
# схемы сумма перезаписывается. Исходные файлы сохраняются как
# scheme.pb.orig и scheme.pb.sha256.orig и повторно не затираются.
#
# Повторный запуск безопасен: уже исправленная схема пропускается.
# Если схема уже перезаписана, а контрольная сумма ещё старая
# (обрыв между двумя загрузками), сумма обновляется, когда рядом есть
# scheme.pb.orig.
#
# Учётные данные S3 — те же переменные, что у ydb-restore.py:
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, S3_ENDPOINT, AWS_S3_PATH_STYLE
#
#   S3_ENDPOINT=https://storage.yandexcloud.net \
#   AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... \
#   AWS_S3_PATH_STYLE=virtual \
#   python3 fix_document_schemes.py my-bucket backups/export1
#
# Зависимость: pip install boto3

import argparse
import hashlib
import logging
import os
import sys
from dataclasses import dataclass

DOCUMENT_ATTRIBUTE = "__document_api_version"
DYNAMODB_ATTRIBUTE_PREFIX = "dynamodb"
SCHEME_NAME = "scheme.pb"
CHECKSUM_NAME = "scheme.pb.sha256"
SCHEME_BACKUP_NAME = "scheme.pb.orig"
CHECKSUM_BACKUP_NAME = "scheme.pb.sha256.orig"


class SchemeError(Exception):
    """Схема не разобрана или запись в S3 делать нельзя."""


@dataclass
class AttrBlock:
    start: int
    end: int
    key: str | None


@dataclass
class Stats:
    scheme_files: int = 0
    updated: int = 0
    skipped: int = 0
    checksums_updated: int = 0
    checksums_repaired: int = 0
    errors: int = 0


def is_scheme_pb(key: str) -> bool:
    return key == SCHEME_NAME or key.endswith("/" + SCHEME_NAME)


def sibling_key(key: str, filename: str) -> str:
    slash = key.rfind("/")
    if slash < 0:
        return filename
    return key[: slash + 1] + filename


def normalize_prefix(prefix: str) -> str:
    prefix = prefix.strip().lstrip("/")
    if prefix in ("", "."):
        return ""
    if prefix == SCHEME_NAME or prefix.endswith("/" + SCHEME_NAME):
        return prefix
    if not prefix.endswith("/"):
        prefix += "/"
    return prefix


def _skip_string(text: str, i: int, limit: int) -> int:
    quote = text[i]
    i += 1
    while i < limit:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == quote:
            return i + 1
        i += 1
    raise SchemeError("незакрытая строка в scheme.pb")


def _skip_line(text: str, i: int, limit: int) -> int:
    newline = text.find("\n", i, limit)
    if newline < 0:
        return limit
    return newline


def _decode_proto_string(literal: str) -> str:
    if len(literal) < 2 or literal[0] not in "\"'" or literal[-1] != literal[0]:
        raise SchemeError("некорректный строковый литерал в scheme.pb")
    body = literal[1:-1]
    out: list[str] = []
    i = 0
    while i < len(body):
        if body[i] != "\\":
            out.append(body[i])
            i += 1
            continue
        i += 1
        if i >= len(body):
            raise SchemeError("оборванный escape в scheme.pb")
        esc = body[i]
        simple = {
            "n": "\n",
            "r": "\r",
            "t": "\t",
            "\\": "\\",
            "'": "'",
            '"': '"',
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "v": "\v",
            "?": "?",
        }
        if esc in simple:
            out.append(simple[esc])
            i += 1
            continue
        if esc == "x":
            hex_digits = body[i + 1 : i + 3]
            if not hex_digits or any(c not in "0123456789abcdefABCDEF" for c in hex_digits):
                raise SchemeError("некорректный \\x escape в scheme.pb")
            out.append(chr(int(hex_digits, 16)))
            i += 1 + len(hex_digits)
            continue
        if esc in "01234567":
            octal = esc
            i += 1
            while i < len(body) and len(octal) < 3 and body[i] in "01234567":
                octal += body[i]
                i += 1
            out.append(chr(int(octal, 8)))
            continue
        if esc in ("u", "U"):
            width = 4 if esc == "u" else 8
            hex_digits = body[i + 1 : i + 1 + width]
            if len(hex_digits) != width or any(c not in "0123456789abcdefABCDEF" for c in hex_digits):
                raise SchemeError("некорректный unicode escape в scheme.pb")
            out.append(chr(int(hex_digits, 16)))
            i += 1 + width
            continue
        raise SchemeError(f"неизвестный escape \\{esc} в scheme.pb")
    return "".join(out)


def _skip_ws(text: str, i: int, limit: int) -> int:
    while i < limit and text[i] in " \t\r\n":
        i += 1
    return i


def _read_strings(text: str, i: int, limit: int) -> tuple[str | None, int]:
    i = _skip_ws(text, i, limit)
    if i < limit and text[i] == ":":
        i += 1
        i = _skip_ws(text, i, limit)
    parts: list[str] = []
    while i < limit and text[i] in "\"'":
        end = _skip_string(text, i, limit)
        parts.append(_decode_proto_string(text[i:end]))
        i = _skip_ws(text, end, limit)
    if not parts:
        return None, i
    return "".join(parts), i


def _extract_key(text: str, begin: int, end: int) -> str | None:
    """Достаёт key из блока attributes { ... }. begin указывает на '{'."""
    i = begin
    depth = 0
    key: str | None = None
    while i < end:
        char = text[i]
        if char in "\"'":
            i = _skip_string(text, i, end)
            continue
        if char == "#":
            i = _skip_line(text, i, end)
            continue
        if char == "/" and i + 1 < end and text[i + 1] == "/":
            i = _skip_line(text, i, end)
            continue
        if char == "{":
            depth += 1
            i += 1
            continue
        if char == "}":
            depth -= 1
            i += 1
            continue
        if char.isascii() and (char.isalpha() or char == "_"):
            start = i
            i += 1
            while i < end and text[i].isascii() and (text[i].isalnum() or text[i] == "_"):
                i += 1
            if depth == 1 and text[start:i] == "key":
                value, i = _read_strings(text, i, end)
                if value is None:
                    raise SchemeError("у атрибута нет строкового поля key")
                if key is not None:
                    raise SchemeError("в блоке attributes несколько полей key")
                key = value
            continue
        i += 1
    return key


def _scan_message(text: str, open_brace: int, limit: int) -> int:
    """open_brace указывает на '{'. Возвращает позицию сразу после парной '}'."""
    if open_brace >= limit or text[open_brace] != "{":
        raise SchemeError("ожидалась '{' в scheme.pb")
    depth = 1
    i = open_brace + 1
    while i < limit:
        char = text[i]
        if char in "\"'":
            i = _skip_string(text, i, limit)
            continue
        if char == "#":
            i = _skip_line(text, i, limit)
            continue
        if char == "/" and i + 1 < limit and text[i + 1] == "/":
            i = _skip_line(text, i, limit)
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise SchemeError("незакрытый блок в scheme.pb")


def _deletion_span(text: str, keyword_start: int, content_end: int) -> tuple[int, int]:
    line_start = text.rfind("\n", 0, keyword_start) + 1
    prefix = text[line_start:keyword_start]
    if prefix.strip():
        return keyword_start, content_end
    end = content_end
    i = content_end
    while i < len(text) and text[i] in " \t":
        i += 1
    if i < len(text) and text[i] == "\r":
        i += 1
    if i < len(text) and text[i] == "\n":
        end = i + 1
    return line_start, end


def _find_attribute_blocks(text: str, begin: int, end: int) -> list[AttrBlock]:
    found: list[AttrBlock] = []
    i = begin
    depth = 0
    while i < end:
        char = text[i]
        if char in "\"'":
            i = _skip_string(text, i, end)
            continue
        if char == "#":
            i = _skip_line(text, i, end)
            continue
        if char == "/" and i + 1 < end and text[i + 1] == "/":
            i = _skip_line(text, i, end)
            continue
        if char == "{":
            depth += 1
            i += 1
            continue
        if char == "}":
            if depth == 0:
                raise SchemeError("лишняя '}' в scheme.pb")
            depth -= 1
            i += 1
            continue
        if char.isascii() and (char.isalpha() or char == "_"):
            keyword_start = i
            i += 1
            while i < end and text[i].isascii() and (text[i].isalnum() or text[i] == "_"):
                i += 1
            if text[keyword_start:i] != "attributes":
                continue
            brace = _skip_ws(text, i, end)
            if brace < end and text[brace] == ":":
                brace = _skip_ws(text, brace + 1, end)
            if brace >= end or text[brace] != "{":
                continue
            close = _scan_message(text, brace, end)
            content_end = close
            if content_end < end and text[content_end] == ";":
                content_end += 1
            key = _extract_key(text, brace, close)
            span_start, span_end = _deletion_span(text, keyword_start, content_end)
            found.append(AttrBlock(span_start, span_end, key))
            found.extend(_find_attribute_blocks(text, brace + 1, close - 1))
            i = close
            continue
        i += 1
    if depth != 0:
        raise SchemeError("незакрытый блок в scheme.pb")
    return found


def attribute_should_go(key: str) -> bool:
    return key == DOCUMENT_ATTRIBUTE or key.startswith(DYNAMODB_ATTRIBUTE_PREFIX)


def rewrite_document_scheme(text: str) -> tuple[str, list[str]] | None:
    """Удаляет атрибуты документной таблицы.

    Возвращает None, если атрибута __document_api_version нет: это обычная
    таблица, и файл менять не нужно. Иначе возвращает новый текст и имена
    удалённых атрибутов в исходном порядке.
    """
    blocks = _find_attribute_blocks(text, 0, len(text))
    if not any(block.key == DOCUMENT_ATTRIBUTE for block in blocks):
        return None
    removable = [block for block in blocks if block.key is not None and attribute_should_go(block.key)]
    if not any(block.key == DOCUMENT_ATTRIBUTE for block in removable):
        return None
    spans = sorted(removable, key=lambda block: (block.start, -(block.end - block.start)))
    chosen: list[AttrBlock] = []
    for block in spans:
        if chosen and block.start >= chosen[-1].start and block.end <= chosen[-1].end:
            continue
        if chosen and block.start < chosen[-1].end:
            raise SchemeError("перекрывающиеся блоки attributes в scheme.pb")
        chosen.append(block)
    pieces: list[str] = []
    cursor = 0
    for block in chosen:
        if block.start < cursor:
            raise SchemeError("перекрывающиеся блоки attributes в scheme.pb")
        pieces.append(text[cursor:block.start])
        cursor = block.end
    pieces.append(text[cursor:])
    rewritten = "".join(pieces)
    left = _find_attribute_blocks(rewritten, 0, len(rewritten))
    if any(block.key is not None and attribute_should_go(block.key) for block in left):
        raise SchemeError("после правки в scheme.pb остались атрибуты документной таблицы")
    return rewritten, [block.key for block in chosen if block.key is not None]


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_checksum_file(content: bytes) -> str | None:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return None
    parts = text.split()
    if not parts:
        return None
    token = parts[0]
    if len(token) == 64 and all(char in "0123456789abcdefABCDEF" for char in token):
        return token.lower()
    return None


def replace_checksum(original: bytes, digest: str) -> bytes:
    """Подменяет сумму, сохраняя хвост исходного файла (пробелы, имя, перевод строки)."""
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise SchemeError("внутренняя ошибка: контрольная сумма не в hex")
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError:
        text = ""
    split_at = len(text)
    for index, char in enumerate(text):
        if char.isspace():
            split_at = index
            break
    head = text[:split_at]
    if head and all(char in "0123456789abcdefABCDEF" for char in head):
        return (digest + text[split_at:]).encode("utf-8")
    return f"{digest} {SCHEME_NAME}".encode("utf-8")


def _s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _require_row_scheme(key: str, text: str) -> None:
    if "columns" not in text or "primary_key" not in text:
        raise SchemeError(
            f"{key}: после удаления атрибутов в схеме не осталось columns/primary_key, запись отменена"
        )


def process_prefix(store, bucket: str, prefix: str, dry_run: bool = False) -> Stats:
    prefix = normalize_prefix(prefix)
    stats = Stats()
    where = _s3_uri(bucket, prefix) if prefix else f"s3://{bucket}/"
    logging.info("листинг %s", where)
    scheme_keys = sorted(key for key in store.list_keys(bucket, prefix) if is_scheme_pb(key))
    stats.scheme_files = len(scheme_keys)
    logging.info("найдено файлов scheme.pb: %s", stats.scheme_files)
    for key in scheme_keys:
        try:
            _process_scheme(store, bucket, key, dry_run, stats)
        except SchemeError as error:
            stats.errors += 1
            logging.error("%s", error)
        except Exception as error:
            stats.errors += 1
            logging.error("%s: %s", _s3_uri(bucket, key), error)
    action = "dry-run, объекты S3 не изменялись" if dry_run else "запись в S3 выполнена"
    logging.info(
        "итого: scheme.pb=%s, обновлено=%s, пропущено=%s, контрольных сумм=%s, "
        "восстановлено сумм=%s, ошибок=%s (%s)",
        stats.scheme_files,
        stats.updated,
        stats.skipped,
        stats.checksums_updated,
        stats.checksums_repaired,
        stats.errors,
        action,
    )
    return stats


def _process_scheme(store, bucket: str, key: str, dry_run: bool, stats: Stats) -> None:
    raw = store.get_object(bucket, key)
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise SchemeError(f"{key}: scheme.pb не в UTF-8") from error
    rewritten = rewrite_document_scheme(text)
    orig_key = sibling_key(key, SCHEME_BACKUP_NAME)
    checksum_key = sibling_key(key, CHECKSUM_NAME)
    checksum_orig_key = sibling_key(key, CHECKSUM_BACKUP_NAME)
    if rewritten is None:
        if store.exists(bucket, orig_key) and store.exists(bucket, checksum_key):
            current = store.get_object(bucket, checksum_key)
            if parse_checksum_file(current) != sha256_hex(raw):
                _write_checksum(
                    store,
                    bucket,
                    checksum_key,
                    checksum_orig_key,
                    current,
                    raw,
                    dry_run,
                )
                stats.checksums_repaired += 1
                logging.info("восстановлена контрольная сумма %s", _s3_uri(bucket, checksum_key))
                return
        stats.skipped += 1
        logging.info("пропуск %s: обычная таблица", _s3_uri(bucket, key))
        return

    new_text, removed = rewritten
    _require_row_scheme(key, new_text)
    new_raw = new_text.encode("utf-8")
    if new_raw == raw:
        raise SchemeError(f"{key}: правка не изменила файл")
    logging.info(
        "%s %s: удаляю атрибуты %s",
        "dry-run" if dry_run else "правка",
        _s3_uri(bucket, key),
        ", ".join(removed),
    )
    if store.exists(bucket, orig_key):
        logging.info("оставляю уже сохранённый оригинал %s", _s3_uri(bucket, orig_key))
    else:
        logging.info(
            "%sсохраняю оригинал %s",
            "dry-run: " if dry_run else "",
            _s3_uri(bucket, orig_key),
        )
        if not dry_run:
            store.copy_object(bucket, key, orig_key)
    checksum_existed = store.exists(bucket, checksum_key)
    old_checksum = store.get_object(bucket, checksum_key) if checksum_existed else None
    if not dry_run:
        store.put_object(bucket, key, new_raw)
    if checksum_existed:
        _write_checksum(
            store,
            bucket,
            checksum_key,
            checksum_orig_key,
            old_checksum,
            new_raw,
            dry_run,
        )
        stats.checksums_updated += 1
    else:
        logging.info("файла контрольной суммы нет: %s", _s3_uri(bucket, checksum_key))
    stats.updated += 1


def _write_checksum(
    store,
    bucket: str,
    checksum_key: str,
    checksum_orig_key: str,
    old_checksum: bytes,
    scheme_bytes: bytes,
    dry_run: bool,
) -> None:
    new_checksum = replace_checksum(old_checksum, sha256_hex(scheme_bytes))
    if parse_checksum_file(new_checksum) != sha256_hex(scheme_bytes):
        raise SchemeError(f"{checksum_key}: не удалось собрать файл контрольной суммы")
    if store.exists(bucket, checksum_orig_key):
        logging.info("оставляю уже сохранённый оригинал %s", _s3_uri(bucket, checksum_orig_key))
    else:
        logging.info(
            "%sсохраняю оригинал %s",
            "dry-run: " if dry_run else "",
            _s3_uri(bucket, checksum_orig_key),
        )
        if not dry_run:
            store.copy_object(bucket, checksum_key, checksum_orig_key)
    logging.info(
        "%sзаписываю контрольную сумму %s",
        "dry-run: " if dry_run else "",
        _s3_uri(bucket, checksum_key),
    )
    if not dry_run:
        store.put_object(bucket, checksum_key, new_checksum)


class BotoS3:
    def __init__(self, client):
        self.client = client

    def list_keys(self, bucket: str, prefix: str):
        token = None
        page = 0
        while True:
            kwargs = {"Bucket": bucket, "Prefix": prefix}
            if token is not None:
                kwargs["ContinuationToken"] = token
            response = self.client.list_objects_v2(**kwargs)
            page += 1
            contents = response.get("Contents") or []
            logging.debug("страница листинга %s, объектов %s", page, len(contents))
            for item in contents:
                key = item.get("Key")
                if key:
                    yield key
            if not response.get("IsTruncated"):
                return
            token = response.get("NextContinuationToken")
            if not token:
                raise SchemeError("листинг S3 оборван: нет NextContinuationToken")

    def get_object(self, bucket: str, key: str) -> bytes:
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        if not isinstance(body, bytes):
            body = bytes(body)
        return body

    def put_object(self, bucket: str, key: str, body: bytes) -> None:
        self.client.put_object(Bucket=bucket, Key=key, Body=body)

    def copy_object(self, bucket: str, source_key: str, dest_key: str) -> None:
        self.client.copy_object(
            Bucket=bucket,
            Key=dest_key,
            CopySource={"Bucket": bucket, "Key": source_key},
        )

    def exists(self, bucket: str, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=bucket, Key=key)
        except ClientError as error:
            status = error.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
            code = str(error.response.get("Error", {}).get("Code", ""))
            if status == 404 or code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


def build_s3_client(endpoint: str | None, path_style: str | None):
    import boto3
    from botocore.client import Config

    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    if not access_key or not secret_key:
        raise SchemeError("не заданы AWS_ACCESS_KEY_ID и AWS_SECRET_ACCESS_KEY")
    if not endpoint:
        raise SchemeError("не задан S3 endpoint: переменная S3_ENDPOINT или флаг --endpoint")
    session = boto3.session.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=os.getenv("AWS_DEFAULT_REGION") or os.getenv("AWS_REGION"),
    )
    if path_style:
        client = session.client(
            service_name="s3",
            endpoint_url=endpoint,
            config=Config(s3={"addressing_style": path_style}),
        )
    else:
        client = session.client(service_name="s3", endpoint_url=endpoint)
    return client


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Удаляет из scheme.pb признаки документных таблиц YDB "
            "(__document_api_version и атрибуты dynamodb*), чтобы import s3 "
            "создавал обычные таблицы. Исходные файлы сохраняются рядом с суффиксом .orig."
        )
    )
    parser.add_argument("bucket", help="имя бакета S3")
    parser.add_argument(
        "prefix",
        help="префикс ключей внутри бакета; обход рекурсивный, листинг читается постранично",
    )
    parser.add_argument(
        "--endpoint",
        default=os.getenv("S3_ENDPOINT"),
        help="URL S3. По умолчанию берётся из S3_ENDPOINT",
    )
    parser.add_argument(
        "--path-style",
        default=os.getenv("AWS_S3_PATH_STYLE"),
        help="addressing style boto3: path или virtual. По умолчанию AWS_S3_PATH_STYLE",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="показать, какие объекты изменились бы, не записывая их в S3",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for name in ("s3transfer", "botocore", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        client = build_s3_client(args.endpoint, args.path_style)
        stats = process_prefix(BotoS3(client), args.bucket, args.prefix, dry_run=args.dry_run)
    except SchemeError as error:
        logging.error("%s", error)
        return 1
    return 1 if stats.errors else 0


if __name__ == "__main__":
    sys.exit(main())
