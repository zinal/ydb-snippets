#!/usr/bin/env python3
"""Проверки сопоставления интерфейсов BareMetal и A-записей без обращения к API."""

from __future__ import annotations

import unittest

from yandex.cloud.baremetal.v2.server_pb2 import (
    NetworkInterface,
    PrivateNetworkInterface,
    PublicNetworkInterface,
    Server,
    VLANSubinterface,
)
from yandex.cloud.dns.v1.dns_zone_pb2 import RecordSet

from register_private_dns import (
    ExistingRecord,
    RegistrationError,
    absolute_name,
    build_inventory,
    ensure_baremetal_endpoint,
    format_change,
    index_a_records,
    list_servers,
    managed_label,
    parse_prefixes,
    plan_changes,
    record_sets_for_batch,
)


def nic(interface_id: str, configuration_id: str, address: str, subnet: str = "subnet") -> NetworkInterface:
    return NetworkInterface(
        network_interface_id=interface_id,
        configuration_network_interface_id=configuration_id,
        mac_address="00:00:00:00:00:01",
        private_interface=PrivateNetworkInterface(
            native_subnet_id=subnet,
            ip_address=address,
        ),
    )


def server(*interfaces: NetworkInterface, name: str = "server1", state: int = Server.RUNNING) -> Server:
    return Server(
        server_id="srv-" + name,
        name=name,
        state=state,
        network_interfaces=list(interfaces),
    )


class InventoryTests(unittest.TestCase):
    def test_two_private_interfaces_use_prefixes_in_configuration_order(self):
        # В ответе API второй порт идёт раньше первого. Префикс выбирается по
        # идентификатору конфигурации, а не по порядку в списке.
        inventory = build_inventory(
            [
                server(
                    nic("nic-b", "2", "10.0.1.5", "subnet-b"),
                    nic("nic-a", "1", "10.0.0.5", "subnet-a"),
                    NetworkInterface(
                        network_interface_id="nic-pub",
                        configuration_network_interface_id="9",
                        public_interface=PublicNetworkInterface(ip_address="203.0.113.10"),
                    ),
                )
            ],
            ("one", "two"),
            "zonne.",
        )
        self.assertEqual(
            {record.fqdn: record.address for record in inventory.desired.values()},
            {
                "server1.one.zonne.": "10.0.0.5",
                "server1.two.zonne.": "10.0.1.5",
            },
        )

    def test_native_address_precedes_vlan_and_empty_native_keeps_its_prefix(self):
        inventory = build_inventory(
            [
                server(
                    NetworkInterface(
                        network_interface_id="nic-a",
                        configuration_network_interface_id="1",
                        private_interface=PrivateNetworkInterface(
                            native_subnet_id="native",
                            ip_address="",
                            vlan_subinterfaces=[
                                VLANSubinterface(tagged_subnet_id="vlan-2", ip_address="10.2.0.8"),
                                VLANSubinterface(tagged_subnet_id="vlan-1", ip_address="10.1.0.8"),
                            ],
                        ),
                    )
                )
            ],
            ("one", "two", "three"),
            "zonne.",
        )
        self.assertEqual(
            {record.fqdn: record.address for record in inventory.desired.values()},
            {
                "server1.two.zonne.": "10.1.0.8",
                "server1.three.zonne.": "10.2.0.8",
            },
        )

    def test_numeric_configuration_ids_sort_as_numbers(self):
        inventory = build_inventory(
            [
                server(
                    nic("nic-10", "10", "10.0.0.10"),
                    nic("nic-2", "2", "10.0.0.2"),
                )
            ],
            ("one", "two"),
            "zonne.",
        )
        self.assertEqual(inventory.desired["server1.one.zonne."].address, "10.0.0.2")
        self.assertEqual(inventory.desired["server1.two.zonne."].address, "10.0.0.10")

    def test_too_many_interfaces_fail_before_any_record_is_implied(self):
        with self.assertRaises(RegistrationError):
            build_inventory(
                [server(nic("nic-a", "1", "10.0.0.1"), nic("nic-b", "2", "10.0.0.2"))],
                ("one",),
                "zonne.",
            )

    def test_public_address_on_private_interface_is_rejected(self):
        with self.assertRaises(RegistrationError):
            build_inventory([server(nic("nic-a", "1", "203.0.113.5"))], ("one",), "zonne.")

    def test_deleting_server_is_not_registered(self):
        inventory = build_inventory(
            [server(nic("nic-a", "1", "10.0.0.4"), name="gone", state=Server.DELETING)],
            ("one",),
            "zonne.",
        )
        self.assertEqual(inventory.desired, {})
        self.assertEqual(inventory.server_names, set())

    def test_invalid_server_name(self):
        with self.assertRaises(RegistrationError):
            build_inventory([server(nic("nic-a", "1", "10.0.0.4"), name="bad_name")], ("one",), "zonne.")


class PlanTests(unittest.TestCase):
    def test_adds_updates_and_deletes_managed_names_only(self):
        zone = "zonne."
        prefixes = ("one", "two")
        desired = build_inventory(
            [server(nic("nic-a", "1", "10.0.0.5"), nic("nic-b", "2", "10.0.1.6"))],
            prefixes,
            zone,
        ).desired
        existing = index_a_records(
            [
                RecordSet(name="server1.one.zonne.", type="A", ttl=60, data=["10.0.0.5"]),
                RecordSet(name="server1.two", type="A", ttl=60, data=["10.0.1.5"], description="old"),
                RecordSet(name="retired.one.zonne.", type="A", ttl=30, data=["10.9.9.9"]),
                RecordSet(name="app.zonne.", type="A", ttl=60, data=["10.0.0.50"]),
                RecordSet(name="note.one.zonne.", type="TXT", ttl=60, data=["keep"]),
            ],
            zone,
        )
        changes = plan_changes(
            desired,
            existing,
            zone=zone,
            prefixes=prefixes,
            ttl=60,
            prune_names=None,
        )
        self.assertEqual([format_change(change) for change in changes], [
            "- retired.one.zonne. 30 A 10.9.9.9",
            "~ server1.two.zonne. 60 A 10.0.1.6 (было 60 A 10.0.1.5)",
        ])
        updated = next(change for change in changes if change.action == "update")
        deletions, additions = record_sets_for_batch([updated])
        self.assertEqual(deletions[0].name, "server1.two")
        self.assertEqual(additions[0].name, "server1.two.zonne.")
        self.assertEqual(list(deletions[0].data), ["10.0.1.5"])
        self.assertEqual(deletions[0].description, "old")
        self.assertEqual(list(additions[0].data), ["10.0.1.6"])
        self.assertEqual(additions[0].ttl, 60)

    def test_filtered_run_does_not_delete_servers_outside_the_selection(self):
        zone = "zonne."
        prefixes = ("one",)
        inventory = build_inventory([server(nic("nic-a", "1", "10.0.0.5"))], prefixes, zone)
        existing = {
            "other.one.zonne.": ExistingRecord("other.one.zonne.", "other.one.zonne.", 60, ("10.1.1.1",), ""),
        }
        changes = plan_changes(
            inventory.desired,
            existing,
            zone=zone,
            prefixes=prefixes,
            ttl=60,
            prune_names=inventory.server_names,
        )
        self.assertEqual([change.action for change in changes], ["add"])

    def test_no_prune_keeps_stale_names_of_the_same_server(self):
        zone = "zonne."
        prefixes = ("one", "two")
        inventory = build_inventory([server(nic("nic-a", "1", "10.0.0.5"))], prefixes, zone)
        existing = index_a_records(
            [RecordSet(name="server1.two.zonne.", type="A", ttl=60, data=["10.0.1.5"])],
            zone,
        )
        changes = plan_changes(
            inventory.desired,
            existing,
            zone=zone,
            prefixes=prefixes,
            ttl=60,
            prune_names=set(),
        )
        self.assertEqual([change.action for change in changes], ["add"])

    def test_ttl_change_replaces_the_record(self):
        zone = "zonne."
        prefixes = ("one",)
        desired = build_inventory([server(nic("nic-a", "1", "10.0.0.5"))], prefixes, zone).desired
        existing = index_a_records(
            [RecordSet(name="server1.one.zonne.", type="A", ttl=300, data=["10.0.0.5"])],
            zone,
        )
        changes = plan_changes(desired, existing, zone=zone, prefixes=prefixes, ttl=60, prune_names=None)
        self.assertEqual(changes[0].action, "update")
        self.assertIn("было 300 A 10.0.0.5", format_change(changes[0]))


class NameTests(unittest.TestCase):
    def test_prefixes_and_managed_names(self):
        self.assertEqual(parse_prefixes(["one,two", "three"]), ("one", "two", "three"))
        with self.assertRaises(RegistrationError):
            parse_prefixes(["one", "one"])
        zone = "zonne."
        self.assertEqual(absolute_name("server1.two", zone), "server1.two.zonne.")
        self.assertEqual(absolute_name("server1.two.zonne.", zone), "server1.two.zonne.")
        self.assertEqual(managed_label("server1.one.zonne.", zone, ("one", "two")), "server1")
        self.assertIsNone(managed_label("app.zonne.", zone, ("one", "two")))
        self.assertIsNone(managed_label("extra.server1.one.zonne.", zone, ("one", "two")))


class PaginationTests(unittest.TestCase):
    def test_list_servers_requests_the_next_page_token(self):
        class Client:
            def __init__(self):
                self.tokens = []

            def ListServers(self, request):
                self.tokens.append(request.page_token)
                if request.page_token == "":
                    return type("Page", (), {"servers": ["first"], "next_page_token": "next"})()
                if request.page_token == "next":
                    return type("Page", (), {"servers": ["second"], "next_page_token": ""})()
                raise AssertionError(request.page_token)

        client = Client()
        self.assertEqual(list_servers(client, "folder", ""), ["first", "second"])
        self.assertEqual(client.tokens, ["", "next"])


class SdkMappingTests(unittest.TestCase):
    def test_baremetal_stub_resolves_to_baremetal_endpoint(self):
        import yandexcloud._sdk as sdk_module
        from yandex.cloud.baremetal.v2.server_service_pb2_grpc import ServerServiceStub

        ensure_baremetal_endpoint()
        self.assertEqual(sdk_module._service_for_ctor(ServerServiceStub), "baremetal")
        ensure_baremetal_endpoint()
        matches = [key for key, _alias in sdk_module._supported_modules if key == "yandex.cloud.baremetal"]
        self.assertEqual(matches, ["yandex.cloud.baremetal"])


if __name__ == "__main__":
    unittest.main()
