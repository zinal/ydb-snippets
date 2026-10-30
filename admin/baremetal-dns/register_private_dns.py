#!/usr/bin/env python3
"""Регистрация приватных адресов Yandex BareMetal во внутренней зоне Cloud DNS.

Для каждого приватного адреса сервера создаётся A-запись

    <имя-сервера>.<префикс>.<зона>

Префиксы задаются по порядку и соответствуют приватным интерфейсам сервера.
Пример: зона ``zonne``, префиксы ``one`` и ``two``. У ``server1`` два приватных
интерфейса, поэтому появляются ``server1.one.zonne`` и ``server1.two.zonne``.

Порядок интерфейсов фиксированный, чтобы имя не переезжало между запусками:

1. Берутся только приватные интерфейсы. Публичный интерфейс не занимает префикс.
2. Они сортируются по ``configuration_network_interface_id``, затем по
   ``network_interface_id``. Числовые идентификаторы сравниваются как числа.
3. У каждого интерфейса сначала идёт адрес native-подсети, затем VLAN-подынтерфейсы
   по ``tagged_subnet_id``.
4. Пустой адрес всё равно занимает свой префикс. Когда DHCP или платформа выдаст
   его позже, остальные имена сервера не сдвинутся.

Каждая A-запись вида ``<метка>.<префикс>.<зона>`` считается записью этого скрипта.
Лишние записи с этими префиксами удаляются. Записи вне этих имён не изменяются.
При ``--filter`` удаляются только записи серверов из этой выборки.

К API скрипт подключается только авторизованным ключом сервисного аккаунта.
Этому аккаунту достаточно ``baremetal.viewer`` на каталог серверов и ``dns.editor``
на саму DNS-зону. Команды выдачи прав — в ``service-account-setup.txt``.
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import logging
import os
import re
import sys
from dataclasses import dataclass

import grpc
from yandex.cloud.baremetal.v2.server_pb2 import Server
from yandex.cloud.baremetal.v2.server_service_pb2 import ListServersRequest
from yandex.cloud.baremetal.v2.server_service_pb2_grpc import ServerServiceStub
from yandex.cloud.dns.v1.dns_zone_pb2 import RecordSet
from yandex.cloud.dns.v1.dns_zone_service_pb2 import (
    GetDnsZoneRequest,
    ListDnsZoneRecordSetsRequest,
    ListDnsZonesRequest,
    UpdateRecordSetsRequest,
)
from yandex.cloud.dns.v1.dns_zone_service_pb2_grpc import DnsZoneServiceStub
from yandexcloud.operations import OperationError

log = logging.getLogger("baremetal-dns")

PAGE_SIZE = 100
# UpdateRecordSets принимает не больше 1000 удалений и 1000 добавлений за раз.
UPDATE_BATCH = 500
DNS_NAME_MAX = 254
_LABEL = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
_RFC1918 = (
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
)


class RegistrationError(Exception):
    """Ошибка конфигурации или несогласованные данные серверов и зоны."""


@dataclass(frozen=True)
class Slot:
    interface_id: str
    configuration_id: str
    mac_address: str
    kind: str
    subnet_id: str
    address: str


@dataclass(frozen=True)
class DesiredRecord:
    fqdn: str
    address: str
    server_name: str
    server_id: str


@dataclass(frozen=True)
class ExistingRecord:
    fqdn: str
    api_name: str
    ttl: int
    data: tuple[str, ...]
    description: str


@dataclass(frozen=True)
class RecordChange:
    action: str
    fqdn: str
    ttl: int
    address: str
    previous_name: str
    previous_ttl: int
    previous_data: tuple[str, ...]
    previous_description: str


@dataclass(frozen=True)
class Inventory:
    desired: dict[str, DesiredRecord]
    server_names: set[str]
    notes: tuple[str, ...]


def is_dns_label(value: str) -> bool:
    return bool(_LABEL.fullmatch(value))


def normalize_zone(value: str) -> str:
    body = value.strip().lower().rstrip(".")
    if not body:
        raise RegistrationError("имя DNS-зоны пустое")
    for label in body.split("."):
        if not is_dns_label(label):
            raise RegistrationError(f"имя DNS-зоны {value!r} содержит недопустимую метку {label!r}")
    return body + "."


def parse_prefixes(values: list[str]) -> tuple[str, ...]:
    raw: list[str] = []
    for value in values:
        raw.extend(part.strip().lower() for part in value.split(","))
    prefixes = tuple(part for part in raw if part)
    if not prefixes:
        raise RegistrationError("нужен хотя бы один префикс, например --prefix one --prefix two")
    seen: set[str] = set()
    for prefix in prefixes:
        if not is_dns_label(prefix):
            raise RegistrationError(f"префикс {prefix!r} не годится как DNS-метка")
        if prefix in seen:
            raise RegistrationError(f"префикс {prefix!r} указан дважды")
        seen.add(prefix)
    return prefixes


def absolute_name(name: str, zone: str) -> str:
    cleaned = name.strip().lower().rstrip(".")
    zone_body = zone.strip().lower().rstrip(".")
    if cleaned == zone_body or cleaned.endswith("." + zone_body):
        return cleaned + "."
    return f"{cleaned}.{zone_body}."


def managed_label(fqdn: str, zone: str, prefixes: tuple[str, ...]) -> str | None:
    absolute = absolute_name(fqdn, zone)
    suffix = "." + zone.strip().lower().rstrip(".") + "."
    if not absolute.endswith(suffix):
        return None
    relative = absolute[: -len(suffix)]
    parts = relative.split(".")
    if len(parts) != 2:
        return None
    label, prefix = parts
    if prefix not in prefixes or not is_dns_label(label):
        return None
    return label


def _natural_key(value: str) -> tuple:
    text = value or ""
    if text.isdigit():
        return (0, int(text), text)
    return (1, text)


def _private_interface(nic):
    has_field = getattr(nic, "HasField", None)
    if has_field is not None:
        if not has_field("private_interface"):
            return None
        return nic.private_interface
    return getattr(nic, "private_interface", None)


def _canonical_private_ip(value: str, server_name: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    try:
        parsed = ipaddress.ip_address(text)
    except ValueError as exc:
        raise RegistrationError(f"{server_name}: некорректный IP-адрес {text!r}") from exc
    if not isinstance(parsed, ipaddress.IPv4Address) or not any(parsed in network for network in _RFC1918):
        raise RegistrationError(
            f"{server_name}: адрес {text} не из частного диапазона 10.0.0.0/8, 172.16.0.0/12 или 192.168.0.0/16"
        )
    return str(parsed)


def private_slots(server) -> list[Slot]:
    server_name = server.name or server.server_id
    private_nics = []
    for nic in server.network_interfaces:
        if _private_interface(nic) is None:
            continue
        private_nics.append(nic)
    private_nics.sort(
        key=lambda nic: (
            _natural_key(nic.configuration_network_interface_id),
            _natural_key(nic.network_interface_id),
        )
    )
    slots: list[Slot] = []
    for nic in private_nics:
        private = _private_interface(nic)
        slots.append(
            Slot(
                interface_id=nic.network_interface_id,
                configuration_id=nic.configuration_network_interface_id,
                mac_address=nic.mac_address,
                kind="native",
                subnet_id=private.native_subnet_id,
                address=_canonical_private_ip(private.ip_address, server_name),
            )
        )
        vlans = sorted(private.vlan_subinterfaces, key=lambda vlan: _natural_key(vlan.tagged_subnet_id))
        for vlan in vlans:
            slots.append(
                Slot(
                    interface_id=nic.network_interface_id,
                    configuration_id=nic.configuration_network_interface_id,
                    mac_address=nic.mac_address,
                    kind="vlan",
                    subnet_id=vlan.tagged_subnet_id,
                    address=_canonical_private_ip(vlan.ip_address, server_name),
                )
            )
    return slots


def _server_label(server) -> str:
    raw = (server.name or "").strip()
    label = raw.lower()
    if not is_dns_label(label):
        raise RegistrationError(
            f"имя сервера {raw!r} (id {server.server_id}) нельзя использовать как DNS-метку"
        )
    return label


def is_active(server) -> bool:
    return int(server.state) != int(Server.DELETING)


def build_inventory(servers, prefixes: tuple[str, ...], zone: str) -> Inventory:
    zone = normalize_zone(zone)
    desired: dict[str, DesiredRecord] = {}
    server_names: set[str] = set()
    notes: list[str] = []
    for server in servers:
        if not is_active(server):
            notes.append(f"пропуск {server.name or server.server_id}: сервер удаляется")
            continue
        label = _server_label(server)
        if label in server_names:
            raise RegistrationError(f"в выборке два сервера с именем {label}")
        server_names.add(label)
        slots = private_slots(server)
        if len(slots) > len(prefixes):
            raise RegistrationError(
                f"{label}: приватных адресов и интерфейсов {len(slots)}, "
                f"а префиксов {len(prefixes)} ({', '.join(prefixes)})"
            )
        if not slots:
            notes.append(f"{label}: приватных интерфейсов нет")
            continue
        for prefix, slot in zip(prefixes, slots):
            fqdn = f"{label}.{prefix}.{zone}"
            if len(fqdn) > DNS_NAME_MAX:
                raise RegistrationError(f"имя {fqdn} длиннее {DNS_NAME_MAX} символов")
            where = (
                f"cfg={slot.configuration_id or '-'} nic={slot.interface_id or '-'} "
                f"{slot.kind} subnet={slot.subnet_id or '-'}"
            )
            if not slot.address:
                notes.append(f"{label}: {where} без адреса, {fqdn} не публикуется")
                continue
            desired[fqdn] = DesiredRecord(
                fqdn=fqdn,
                address=slot.address,
                server_name=label,
                server_id=server.server_id,
            )
            notes.append(f"{label}: {where} {slot.address} -> {fqdn}")
    return Inventory(desired=desired, server_names=server_names, notes=tuple(notes))


def index_a_records(record_sets, zone: str) -> dict[str, ExistingRecord]:
    indexed: dict[str, ExistingRecord] = {}
    for record in record_sets:
        if record.type != "A":
            continue
        fqdn = absolute_name(record.name, zone)
        if fqdn in indexed:
            raise RegistrationError(f"в зоне две A-записи с именем {fqdn}")
        indexed[fqdn] = ExistingRecord(
            fqdn=fqdn,
            api_name=record.name,
            ttl=int(record.ttl),
            data=tuple(record.data),
            description=record.description,
        )
    return indexed


def plan_changes(
    desired: dict[str, DesiredRecord],
    existing: dict[str, ExistingRecord],
    *,
    zone: str,
    prefixes: tuple[str, ...],
    ttl: int,
    prune_names: set[str] | None,
) -> list[RecordChange]:
    managed = {
        fqdn: record
        for fqdn, record in existing.items()
        if managed_label(fqdn, zone, prefixes) is not None
    }
    changes: list[RecordChange] = []
    for fqdn in sorted(set(desired) | set(managed)):
        want = desired.get(fqdn)
        have = managed.get(fqdn)
        if want is not None and have is not None and have.ttl == ttl and have.data == (want.address,):
            continue
        if want is None:
            assert have is not None
            label = managed_label(fqdn, zone, prefixes)
            if prune_names is not None and label not in prune_names:
                continue
            changes.append(
                RecordChange(
                    action="delete",
                    fqdn=fqdn,
                    ttl=0,
                    address="",
                    previous_name=have.api_name,
                    previous_ttl=have.ttl,
                    previous_data=have.data,
                    previous_description=have.description,
                )
            )
            continue
        if have is None:
            changes.append(
                RecordChange(
                    action="add",
                    fqdn=fqdn,
                    ttl=ttl,
                    address=want.address,
                    previous_name="",
                    previous_ttl=0,
                    previous_data=(),
                    previous_description="",
                )
            )
            continue
        changes.append(
            RecordChange(
                action="update",
                fqdn=fqdn,
                ttl=ttl,
                address=want.address,
                previous_name=have.api_name,
                previous_ttl=have.ttl,
                previous_data=have.data,
                previous_description=have.description,
            )
        )
    return changes


def format_change(change: RecordChange) -> str:
    if change.action == "add":
        return f"+ {change.fqdn} {change.ttl} A {change.address}"
    previous = " ".join(change.previous_data)
    if change.action == "delete":
        return f"- {change.fqdn} {change.previous_ttl} A {previous}"
    return f"~ {change.fqdn} {change.ttl} A {change.address} (было {change.previous_ttl} A {previous})"


def record_sets_for_batch(changes: list[RecordChange]) -> tuple[list[RecordSet], list[RecordSet]]:
    deletions: list[RecordSet] = []
    additions: list[RecordSet] = []
    for change in changes:
        if change.action in ("delete", "update"):
            deletions.append(
                RecordSet(
                    name=change.previous_name,
                    type="A",
                    ttl=change.previous_ttl,
                    data=list(change.previous_data),
                    description=change.previous_description,
                )
            )
        if change.action in ("add", "update"):
            additions.append(
                RecordSet(
                    name=change.fqdn,
                    type="A",
                    ttl=change.ttl,
                    data=[change.address],
                )
            )
    return deletions, additions


def chunks(items: list, size: int):
    if size < 1:
        raise ValueError("размер пакета должен быть положительным")
    for start in range(0, len(items), size):
        yield items[start : start + size]


def ensure_baremetal_endpoint() -> None:
    """Пакет yandexcloud содержит stub BareMetal, но не сопоставляет его с endpoint.

    Идентификатор сервиса в каталоге endpoint — ``baremetal``
    (``baremetal.api.cloud.yandex.net:443``).
    """
    import yandexcloud._sdk as sdk_module

    modules = sdk_module._supported_modules
    if any(key == "yandex.cloud.baremetal" or key.startswith("yandex.cloud.baremetal.") for key, _alias in modules):
        return
    modules.insert(0, ("yandex.cloud.baremetal", "baremetal"))


def call_rpc(func):
    try:
        return func()
    except grpc.RpcError as exc:
        detail = exc.details() if hasattr(exc, "details") else None
        raise RegistrationError(detail or str(exc)) from exc


def list_servers(client, folder_id: str, server_filter: str) -> list:
    servers = []
    token = ""
    while True:
        request = ListServersRequest(
            folder_id=folder_id,
            page_size=PAGE_SIZE,
            page_token=token,
            filter=server_filter,
        )
        response = call_rpc(lambda request=request: client.ListServers(request))
        servers.extend(response.servers)
        token = response.next_page_token
        if not token:
            return servers


def resolve_zone(client, zone_id: str, zone_name: str, folder_id: str) -> tuple[str, str]:
    if zone_id:
        request = GetDnsZoneRequest(dns_zone_id=zone_id)
        zone = call_rpc(lambda request=request: client.Get(request))
        normalized = normalize_zone(zone.zone)
        if zone_name and normalize_zone(zone_name) != normalized:
            raise RegistrationError(
                f"зона {zone_id} имеет суффикс {normalized}, а не {normalize_zone(zone_name)}"
            )
        return zone.id, normalized

    want = normalize_zone(zone_name)
    matched = []
    token = ""
    while True:
        request = ListDnsZonesRequest(folder_id=folder_id, page_size=PAGE_SIZE, page_token=token)
        response = call_rpc(lambda request=request: client.List(request))
        for zone in response.dns_zones:
            if normalize_zone(zone.zone) == want:
                matched.append(zone)
        token = response.next_page_token
        if not token:
            break
    if not matched:
        raise RegistrationError(f"в каталоге {folder_id} нет DNS-зоны {want}")
    if len(matched) > 1:
        ids = ", ".join(zone.id for zone in matched)
        raise RegistrationError(f"зона {want} найдена несколько раз: {ids}. Укажите --zone-id")
    return matched[0].id, want


def list_a_records(client, zone_id: str):
    records = []
    token = ""
    while True:
        request = ListDnsZoneRecordSetsRequest(
            dns_zone_id=zone_id,
            page_size=PAGE_SIZE,
            page_token=token,
            filter='type="A"',
        )
        response = call_rpc(lambda request=request: client.ListRecordSets(request))
        records.extend(response.record_sets)
        token = response.next_page_token
        if not token:
            return records


def prune_scope(server_names: set[str], *, filtered: bool, prune: bool) -> set[str] | None:
    """None означает удалять любую чужую A-запись под заданными префиксами.

    При фильтре серверов или ``--no-prune`` удаление ограничено: фильтр не должен
    снимать записи серверов, которых нет в этой выборке.
    """
    if not prune:
        return set()
    if filtered:
        return set(server_names)
    return None


def apply_changes(sdk, client, zone_id: str, changes: list[RecordChange], timeout: float) -> None:
    for batch in chunks(changes, UPDATE_BATCH):
        deletions, additions = record_sets_for_batch(batch)
        request = UpdateRecordSetsRequest(
            dns_zone_id=zone_id,
            deletions=deletions,
            additions=additions,
        )
        operation = call_rpc(lambda request=request: client.UpdateRecordSets(request))
        try:
            sdk.wait_operation_and_get_result(operation, timeout=timeout)
        except OperationError as exc:
            raise RegistrationError(str(exc)) from exc


def load_service_account_key(path: str) -> dict:
    if not path:
        raise RegistrationError("укажите --sa-key-file или переменную YC_SERVICE_ACCOUNT_KEY_FILE")
    try:
        with open(path, encoding="utf-8") as key_file:
            key = json.load(key_file)
    except FileNotFoundError as exc:
        raise RegistrationError(f"файл ключа сервисного аккаунта не найден: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RegistrationError(f"файл ключа {path} не является JSON") from exc
    if not isinstance(key, dict):
        raise RegistrationError(f"файл ключа {path} должен содержать JSON-объект")
    missing = [field for field in ("id", "service_account_id", "private_key") if not key.get(field)]
    if missing:
        raise RegistrationError(
            f"в {path} нет полей авторизованного ключа: {', '.join(missing)}. "
            "Создайте ключ командой yc iam key create, см. service-account-setup.txt"
        )
    private_key = key["private_key"]
    if not isinstance(private_key, str) or "-----BEGIN PRIVATE KEY-----" not in private_key:
        raise RegistrationError(f"в {path} поле private_key не похоже на ключ из yc iam key create")
    return key


def build_sdk(sa_key_file: str, endpoint: str):
    import yandexcloud

    if endpoint:
        yandexcloud.set_up_yc_api_endpoint(endpoint)
    sdk_kwargs = {"service_account_key": load_service_account_key(sa_key_file)}
    if endpoint:
        sdk_kwargs["endpoint"] = endpoint
    return yandexcloud.SDK(**sdk_kwargs)


def run(args: argparse.Namespace) -> list[RecordChange]:
    if not args.folder_id:
        raise RegistrationError("укажите --folder-id или переменную YC_FOLDER_ID")
    if not args.zone_id and not args.zone:
        raise RegistrationError("укажите --zone-id или --zone")
    if args.ttl < 0 or args.ttl > 2147483647:
        raise RegistrationError("--ttl должен быть от 0 до 2147483647")
    prefixes = parse_prefixes(args.prefixes)
    sdk = build_sdk(args.sa_key_file, args.endpoint)
    ensure_baremetal_endpoint()
    baremetal = sdk.client(ServerServiceStub)
    dns = sdk.client(DnsZoneServiceStub)

    servers = list_servers(baremetal, args.folder_id, args.filter or "")
    log.info("серверов в выборке: %s", len(servers))
    dns_folder = args.dns_folder_id or args.folder_id
    zone_id, zone = resolve_zone(dns, args.zone_id or "", args.zone or "", dns_folder)
    inventory = build_inventory(servers, prefixes, zone)
    for note in inventory.notes:
        log.info("%s", note)

    existing = index_a_records(list_a_records(dns, zone_id), zone)
    changes = plan_changes(
        inventory.desired,
        existing,
        zone=zone,
        prefixes=prefixes,
        ttl=args.ttl,
        prune_names=prune_scope(
            inventory.server_names,
            filtered=bool(args.filter),
            prune=not args.no_prune,
        ),
    )
    if not changes:
        log.info("зона %s уже соответствует адресам серверов", zone)
        return []
    for change in changes:
        print(format_change(change))
    if args.dry_run:
        log.info("dry-run: записи не изменены")
        return changes
    apply_changes(sdk, dns, zone_id, changes, args.timeout)
    log.info("обновлено записей: %s", len(changes))
    return changes


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Синхронизирует A-записи указанной зоны Cloud DNS "
            "с приватными адресами серверов Yandex BareMetal."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""пример:
  python register_private_dns.py \\
    --sa-key-file ~/.config/yc/baremetal-dns-key.json \\
    --folder-id b1g123456789******** \\
    --zone-id dns123456789******** \\
    --prefix one --prefix two

Сервер server1 с двумя приватными интерфейсами получит имена
server1.one.zonne и server1.two.zonne. Повторите запуск по расписанию:
скрипт обновит адрес, если платформа выдала другой, и снимет запись
удалённого сервера.

Ключ сервисного аккаунта обязателен: --sa-key-file или
YC_SERVICE_ACCOUNT_KEY_FILE. Как создать аккаунт, выдать роли и ключ,
написано в service-account-setup.txt.
""",
    )
    parser.add_argument("--folder-id", default=os.environ.get("YC_FOLDER_ID", ""), help="каталог с серверами BareMetal")
    parser.add_argument(
        "--dns-folder-id",
        default=os.environ.get("YC_DNS_FOLDER_ID", ""),
        help="каталог DNS-зоны, если он отличается от каталога серверов; нужен при поиске по --zone",
    )
    parser.add_argument("--zone-id", default="", help="идентификатор зоны Cloud DNS")
    parser.add_argument("--zone", default="", help="суффикс зоны, например zonne или zonne.")
    parser.add_argument(
        "--prefix",
        action="append",
        dest="prefixes",
        required=True,
        help="промежуточное имя интерфейса; повторите флаг или перечислите через запятую: one,two",
    )
    parser.add_argument("--ttl", type=int, default=60, help="TTL A-записей в секундах (по умолчанию 60)")
    parser.add_argument("--filter", default="", help='фильтр ListServers, например \'name : "prod"\'')
    parser.add_argument("--dry-run", action="store_true", help="показать изменения и не вызывать UpdateRecordSets")
    parser.add_argument(
        "--no-prune",
        action="store_true",
        help="не удалять устаревшие A-записи; адреса существующих имён всё равно обновляются",
    )
    parser.add_argument(
        "--sa-key-file",
        default=os.environ.get("YC_SERVICE_ACCOUNT_KEY_FILE") or "",
        help="JSON авторизованного ключа сервисного аккаунта (или YC_SERVICE_ACCOUNT_KEY_FILE)",
    )
    parser.add_argument("--endpoint", default=os.environ.get("YC_API_ENDPOINT") or "", help="корень API, если это не api.cloud.yandex.net")
    parser.add_argument("--timeout", type=float, default=180, help="ожидание операции DNS, секунды")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        run(parse_args(argv))
    except RegistrationError as exc:
        log.error("ошибка: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
