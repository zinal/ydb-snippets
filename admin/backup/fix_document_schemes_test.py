#! /usr/bin/env python3

import hashlib
import subprocess
import unittest
from pathlib import Path

import fix_document_schemes as fix

SAMPLE = Path(__file__).resolve().parent / "testdata" / "scheme.pb"
SAMPLE_SHA = Path(__file__).resolve().parent / "testdata" / "scheme.pb.sha256"

MINIMAL = """\
columns {
  name: "id"
  type {
    optional_type {
      item {
        type_id: UINT64
      }
    }
  }
}
primary_key: "id"
attributes {
  key: "__document_api_version"
  value: "1"
}
attributes {
  key: "dynamodbIndexes"
  value: "{\\"a\\":\\"}\\"}"
}
attributes {
  key: "user_note"
  value: "a}b{c"
}
"""


class MemS3:
    def __init__(self, objects):
        self.objects = {(bucket, key): bytes(body) for (bucket, key), body in objects.items()}
        self.puts = []
        self.copies = []

    def list_keys(self, bucket, prefix):
        for (stored_bucket, key) in sorted(self.objects):
            if stored_bucket == bucket and key.startswith(prefix):
                yield key

    def get_object(self, bucket, key):
        return self.objects[(bucket, key)]

    def put_object(self, bucket, key, body):
        self.puts.append(key)
        self.objects[(bucket, key)] = bytes(body)

    def copy_object(self, bucket, source_key, dest_key):
        self.copies.append((source_key, dest_key))
        self.objects[(bucket, dest_key)] = bytes(self.objects[(bucket, source_key)])

    def exists(self, bucket, key):
        return (bucket, key) in self.objects


class RewriteTest(unittest.TestCase):
    def test_sample_checksum_matches_exporter_format(self):
        body = SAMPLE.read_bytes()
        checksum = SAMPLE_SHA.read_bytes()
        self.assertEqual(checksum, f"{hashlib.sha256(body).hexdigest()} scheme.pb".encode())
        self.assertFalse(checksum.endswith(b"\n"))

    def test_sample_document_attributes_removed_and_rest_kept(self):
        original = SAMPLE.read_text(encoding="utf-8")
        rewritten = fix.rewrite_document_scheme(original)
        self.assertIsNotNone(rewritten)
        text, removed = rewritten
        self.assertEqual(
            removed,
            ["__document_api_version", "dynamodbDataColumns", "dynamodbIndexes"],
        )
        head, _, _ = original.partition("attributes {")
        tail = original[original.rindex("}\npartitioning_settings {") :]
        self.assertTrue(text.startswith(head))
        self.assertTrue(text.endswith(tail))
        self.assertNotIn("attributes {", text)
        self.assertNotIn("__document_api_version", text)
        self.assertNotIn("dynamodb", text)
        self.assertIn('name: "ix1"', text)
        self.assertIn('data_columns: "__RowData"', text)
        again = fix.rewrite_document_scheme(text)
        self.assertIsNone(again)

    def test_sample_checksum_file_validates_with_sha256sum(self):
        original = SAMPLE.read_bytes()
        text, _ = fix.rewrite_document_scheme(original.decode("utf-8"))
        new_body = text.encode("utf-8")
        checksum = fix.replace_checksum(SAMPLE_SHA.read_bytes(), fix.sha256_hex(new_body))
        self.assertFalse(checksum.endswith(b"\n"))
        self.assertTrue(checksum.endswith(b" scheme.pb"))
        directory = Path(__file__).resolve().parent / "testdata"
        scratch = directory / ".tmp-scheme-check"
        scratch.mkdir(exist_ok=True)
        try:
            (scratch / "scheme.pb").write_bytes(new_body)
            (scratch / "scheme.pb.sha256").write_bytes(checksum)
            result = subprocess.run(
                ["sha256sum", "-c", "scheme.pb.sha256"],
                cwd=scratch,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        finally:
            for path in scratch.iterdir():
                path.unlink()
            scratch.rmdir()

    def test_keeps_unrelated_attribute_and_braces_inside_strings(self):
        text, removed = fix.rewrite_document_scheme(MINIMAL)
        self.assertEqual(removed, ["__document_api_version", "dynamodbIndexes"])
        self.assertIn('key: "user_note"', text)
        self.assertIn('value: "a}b{c"', text)
        self.assertNotIn("dynamodb", text)
        self.assertNotIn("__document_api_version", text)

    def test_regular_table_is_not_modified(self):
        regular = MINIMAL.split("attributes {", 1)[0]
        self.assertIsNone(fix.rewrite_document_scheme(regular))

    def test_marker_inside_comment_or_column_name_is_not_enough(self):
        comment_only = 'columns {\n  name: "id"\n}\nprimary_key: "id"\n# attributes { key: "__document_api_version" value: "1" }\n'
        self.assertIsNone(fix.rewrite_document_scheme(comment_only))
        column = (
            'columns {\n  name: "__document_api_version"\n}\n'
            'primary_key: "id"\n'
            'attributes {\n  key: "user_note"\n  value: "x"\n}\n'
        )
        self.assertIsNone(fix.rewrite_document_scheme(column))

    def test_crlf_and_kept_attribute_layout(self):
        text = MINIMAL.replace("\n", "\r\n")
        rewritten, _ = fix.rewrite_document_scheme(text)
        self.assertIn("\r\n", rewritten)
        self.assertNotIn("\nuser_note", rewritten.replace("\r\n", "\n"))
        self.assertIn('key: "user_note"', rewritten)

    def test_nested_dynamodb_attribute_removed_user_attribute_kept(self):
        text = """\
columns {
  name: "id"
}
primary_key: "id"
attributes {
  key: "user_note"
  value: "keep"
  attributes {
    key: "dynamodbNested"
    value: "drop"
  }
}
attributes {
  key: "__document_api_version"
  value: "1"
}
"""
        rewritten, removed = fix.rewrite_document_scheme(text)
        self.assertIn("dynamodbNested", removed)
        self.assertIn("__document_api_version", removed)
        self.assertIn('key: "user_note"', rewritten)
        self.assertNotIn("dynamodbNested", rewritten)
        self.assertNotIn("__document_api_version", rewritten)

    def test_string_containing_fake_block_is_not_parsed_as_attribute(self):
        text = """\
columns {
  name: "attributes { key: \\"dynamodbNope\\" }"
}
primary_key: "id"
attributes {
  key: "__document_api_version"
  value: "1"
}
"""
        rewritten, removed = fix.rewrite_document_scheme(text)
        self.assertEqual(removed, ["__document_api_version"])
        self.assertIn('name: "attributes { key: \\"dynamodbNope\\" }"', rewritten)

    def test_checksum_tail_is_preserved(self):
        digest = "ab" * 32
        two_spaces = b"00" * 32 + b"  scheme.pb\n"
        self.assertEqual(fix.replace_checksum(two_spaces, digest), (digest + "  scheme.pb\n").encode())
        self.assertEqual(fix.parse_checksum_file(two_spaces), "00" * 32)

    def test_colon_and_semicolon_form_keeps_other_attributes(self):
        text = """\
columns {
  name: "id"
}
primary_key: "id"
attributes: {
  key: "__document_api_version"
  value: "1"
};
attributes: {
  key: "dynamodbIndexes"
  value: "z"
};
attributes: {
  key: "keep_me"
  value: "ok"
};
"""
        rewritten, removed = fix.rewrite_document_scheme(text)
        self.assertEqual(removed, ["__document_api_version", "dynamodbIndexes"])
        self.assertIn('key: "keep_me"', rewritten)
        self.assertIn('value: "ok"', rewritten)
        self.assertTrue(rewritten.rstrip().endswith(";"))
        self.assertNotIn("dynamodb", rewritten)

    def test_prefix_and_scheme_name(self):
        self.assertEqual(fix.normalize_prefix("/backup/export"), "backup/export/")
        self.assertEqual(fix.normalize_prefix("backup/export/"), "backup/export/")
        self.assertEqual(fix.normalize_prefix("."), "")
        self.assertEqual(fix.normalize_prefix("backup/t/scheme.pb"), "backup/t/scheme.pb")
        self.assertTrue(fix.is_scheme_pb("a/scheme.pb"))
        self.assertTrue(fix.is_scheme_pb("scheme.pb"))
        self.assertFalse(fix.is_scheme_pb("a/scheme.pb.sha256"))
        self.assertFalse(fix.is_scheme_pb("a/scheme.pb.orig"))
        self.assertFalse(fix.is_scheme_pb("a/notscheme.pb"))
        self.assertEqual(fix.sibling_key("a/b/scheme.pb", "scheme.pb.orig"), "a/b/scheme.pb.orig")
        self.assertEqual(fix.sibling_key("scheme.pb", "scheme.pb.sha256"), "scheme.pb.sha256")


class PagingClient:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list_objects_v2(self, **kwargs):
        self.calls.append(kwargs)
        token = kwargs.get("ContinuationToken")
        index = 0 if token is None else int(token)
        return self.pages[index]


class ListingTest(unittest.TestCase):
    def test_listing_follows_continuation_token(self):
        client = PagingClient(
            [
                {
                    "Contents": [{"Key": "root/t/scheme.pb"}, {"Key": "root/t/data_00.csv"}],
                    "IsTruncated": True,
                    "NextContinuationToken": "1",
                },
                {
                    "Contents": [{"Key": "root/u/scheme.pb"}, {"Key": "root/u/scheme.pb.sha256"}],
                    "IsTruncated": False,
                },
            ]
        )
        keys = list(fix.BotoS3(client).list_keys("bucket", "root/"))
        self.assertEqual(
            keys,
            ["root/t/scheme.pb", "root/t/data_00.csv", "root/u/scheme.pb", "root/u/scheme.pb.sha256"],
        )
        self.assertEqual(client.calls[1]["ContinuationToken"], "1")
        self.assertEqual(client.calls[0]["Prefix"], "root/")

    def test_truncated_listing_without_token_fails(self):
        client = PagingClient([{"Contents": [], "IsTruncated": True}])
        with self.assertRaises(fix.SchemeError):
            list(fix.BotoS3(client).list_keys("bucket", ""))


class ProcessTest(unittest.TestCase):
    def setUp(self):
        self.scheme = SAMPLE.read_bytes()
        self.checksum = SAMPLE_SHA.read_bytes()
        regular = b'columns {\n  name: "id"\n}\nprimary_key: "id"\n'
        self.store = MemS3(
            {
                ("b", "exp/doc/scheme.pb"): self.scheme,
                ("b", "exp/doc/scheme.pb.sha256"): self.checksum,
                ("b", "exp/doc/data_00.csv"): b"id\n1\n",
                ("b", "exp/plain/scheme.pb"): regular,
                ("b", "exp/plain/scheme.pb.sha256"): b"deadbeef scheme.pb",
                ("b", "other/scheme.pb"): self.scheme,
            }
        )

    def test_updates_document_table_and_reserves_originals(self):
        stats = fix.process_prefix(self.store, "b", "exp")
        self.assertEqual(stats.errors, 0)
        self.assertEqual(stats.scheme_files, 2)
        self.assertEqual(stats.updated, 1)
        self.assertEqual(stats.skipped, 1)
        self.assertEqual(stats.checksums_updated, 1)
        original_scheme = self.store.objects[("b", "exp/doc/scheme.pb.orig")]
        original_sum = self.store.objects[("b", "exp/doc/scheme.pb.sha256.orig")]
        self.assertEqual(original_scheme, self.scheme)
        self.assertEqual(original_sum, self.checksum)
        new_scheme = self.store.objects[("b", "exp/doc/scheme.pb")]
        self.assertNotEqual(new_scheme, self.scheme)
        self.assertNotIn(b"__document_api_version", new_scheme)
        self.assertNotIn(b"dynamodb", new_scheme)
        new_sum = self.store.objects[("b", "exp/doc/scheme.pb.sha256")]
        self.assertEqual(fix.parse_checksum_file(new_sum), hashlib.sha256(new_scheme).hexdigest())
        self.assertTrue(new_sum.endswith(b" scheme.pb"))
        self.assertEqual(self.store.objects[("b", "exp/plain/scheme.pb")], b'columns {\n  name: "id"\n}\nprimary_key: "id"\n')
        self.assertEqual(self.store.objects[("b", "other/scheme.pb")], self.scheme)
        self.assertNotIn(("b", "exp/plain/scheme.pb.orig"), self.store.objects)

        puts_before = list(self.store.puts)
        stats = fix.process_prefix(self.store, "b", "/exp/")
        self.assertEqual(stats.updated, 0)
        self.assertEqual(stats.skipped, 2)
        self.assertEqual(stats.checksums_repaired, 0)
        self.assertEqual(self.store.puts, puts_before)
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb.orig")], self.scheme)

    def test_dry_run_does_not_write(self):
        stats = fix.process_prefix(self.store, "b", "exp/", dry_run=True)
        self.assertEqual(stats.updated, 1)
        self.assertEqual(self.store.puts, [])
        self.assertEqual(self.store.copies, [])
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb")], self.scheme)

    def test_does_not_overwrite_existing_original(self):
        self.store.objects[("b", "exp/doc/scheme.pb.orig")] = b"first-original"
        self.store.objects[("b", "exp/doc/scheme.pb.sha256.orig")] = b"first-sum"
        stats = fix.process_prefix(self.store, "b", "exp/")
        self.assertEqual(stats.errors, 0)
        self.assertEqual(stats.updated, 1)
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb.orig")], b"first-original")
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb.sha256.orig")], b"first-sum")

    def test_repairs_checksum_when_scheme_was_already_rewritten(self):
        text, _ = fix.rewrite_document_scheme(self.scheme.decode("utf-8"))
        cleaned = text.encode("utf-8")
        self.store.objects[("b", "exp/doc/scheme.pb")] = cleaned
        self.store.objects[("b", "exp/doc/scheme.pb.orig")] = self.scheme
        stats = fix.process_prefix(self.store, "b", "exp/")
        self.assertEqual(stats.updated, 0)
        self.assertEqual(stats.checksums_repaired, 1)
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb")], cleaned)
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb.orig")], self.scheme)
        self.assertEqual(self.store.objects[("b", "exp/doc/scheme.pb.sha256.orig")], self.checksum)
        new_sum = self.store.objects[("b", "exp/doc/scheme.pb.sha256")]
        self.assertEqual(fix.parse_checksum_file(new_sum), hashlib.sha256(cleaned).hexdigest())

    def test_scheme_without_checksum_is_still_rewritten(self):
        del self.store.objects[("b", "exp/doc/scheme.pb.sha256")]
        stats = fix.process_prefix(self.store, "b", "exp/")
        self.assertEqual(stats.errors, 0)
        self.assertEqual(stats.updated, 1)
        self.assertEqual(stats.checksums_updated, 0)
        self.assertIn(("b", "exp/doc/scheme.pb.orig"), self.store.objects)
        self.assertNotIn(("b", "exp/doc/scheme.pb.sha256"), self.store.objects)


if __name__ == "__main__":
    unittest.main()
