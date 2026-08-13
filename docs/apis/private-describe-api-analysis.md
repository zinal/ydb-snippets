# Анализ API: `db schema execute` и `viewer/json/describe`

Документ суммирует разбор внутреннего CLI/viewer API и доступных аналогов через HTTP и gRPC (включая legacy).

---

## 1. `ydbd db schema execute file.txt`

### Команда

```bash
ydbd -s grpcs://host:2135 --ca-file ca.crt --token-file ydb-token db schema execute file.txt
```

### Реализация

Класс: `TClientCommandSchemaExec`  
Файл: `ydb/core/driver_lib/cli_base/cli_cmds_db.cpp`

Цепочка:

1. `file.txt` парсится как text-protobuf `NKikimrSchemeOp::TModifyScript` (`repeated ModifyScheme`).
2. Каждый `ModifyScheme` превращается в отдельный `NKikimrClient::TSchemeOperation`.
3. При `-s grpcs://...` запрос уходит в legacy gRPC `TGRpcServer.SchemeOperation`.
4. На сервере: MessageBusProxy → TxProxy → SchemeShard.
5. При статусе `INPROGRESS` клиент сам поллит `SchemeOperationStatus`.

Формат файла (`TModifyScript`):

```protobuf
ModifyScheme {
  WorkingDir: "/Root/test"
  OperationType: ESchemeOpCreateTable
  CreateTable {
    Name: "temp_mytab1"
    CopyFromTable: "/Root/test/mytab1"
    PartitionConfig {
      ColumnFamilies {
        Id: 0
        Name: "default"
        StorageConfig {
          SysLog { PreferredPoolKind: "sdd" }
          Log { PreferredPoolKind: "sdd" }
          Data { PreferredPoolKind: "sdd" }
        }
      }
    }
  }
}
```

Ключевые proto:

| Сообщение | Где |
|---|---|
| `TModifyScript` | `ydb/core/protos/flat_scheme_op.proto` |
| `TSchemeOperation` | `ydb/core/protos/msgbus.proto` |
| `rpc SchemeOperation` | `ydb/core/protos/grpc.proto` (legacy `TGRpcServer`) |

---

## 2. Можно ли вызвать `schema execute` через HTTP?

### Короткий ответ

**В типичном production-`ydbd` — нет.**  
HTTP-обёртка MessageBus (`/CLI_MB/SchemeOperation`) в коде есть, но на порту Embedded UI / monitoring **не поднимается**.

### Как устроен MessageBus HTTP (если бы был включён)

- Путь: `POST /CLI_MB/SchemeOperation`
- Body: JSON `TSchemeOperation` (не text-protobuf `TModifyScript` as-is)
- Auth: заголовок `Authorization` → `SecurityToken`
- Регистрация: `TMessageBusHttpServer` → `AppData()->Mon->Register(this)`  
  (`ydb/core/client/server/msgbus_http_server.cpp`)

Имя сервиса `"CLI_MB"` задаётся в протоколе:

```cpp
// ydb/public/lib/base/msgbus.h
TProtocol(int port)
    : NBus::TBusBufferProtocol("CLI_MB", port)
```

### Почему `/CLI_MB` недоступен в обычном запуске

1. HTTP-сервер MessageBus создаётся только в `TMessageBusServer::InitSession`.
2. `InitSession` вызывается только если у proxy есть ненулевой `Server`:

```cpp
// ydb/core/client/server/msgbus_server_proxy.cpp
if (Server) {
    Server->InitSession(ctx.ActorSystem(), ctx.SelfID);
}
```

3. В production runner (`run.cpp`) добавляется `TGRpcServicesInitializer`, который создаёт:

```cpp
CreateMessageBusServerProxy(nullptr);  // Server == nullptr → InitSession не вызывается
```

4. `TMessageBusServicesInitializer` (путь с реальным `CreateMsgBusServer`) в `run.cpp` **не подключён**.
5. `CreateMsgBusServer` фактически используется в тестах (`ydb/core/testlib/test_client.cpp`).

| Конфигурация | `/CLI_MB` на mon-порту |
|---|---|
| Обычный `ydbd` (gRPC) | нет |
| Тесты с `CreateMsgBusServer` | да |

### Рабочий внешний аналог

Legacy gRPC на порту `2135`:

```text
TGRpcServer.SchemeOperation(TSchemeOperation) → TResponse
```

Это тот же путь, которым пользуется CLI при `-s grpcs://...`.

### Пример тела (эквивалент одного `ModifyScheme`)

Если бы MessageBus HTTP был доступен, body выглядел бы так:

```json
{
  "Transaction": {
    "ModifyScheme": {
      "WorkingDir": "/Root/test",
      "OperationType": "ESchemeOpCreateTable",
      "CreateTable": {
        "Name": "temp_mytab1",
        "CopyFromTable": "/Root/test/mytab1",
        "PartitionConfig": {
          "ColumnFamilies": [
            {
              "Id": 0,
              "Name": "default",
              "StorageConfig": {
                "SysLog": { "PreferredPoolKind": "sdd" },
                "Log": { "PreferredPoolKind": "sdd" },
                "Data": { "PreferredPoolKind": "sdd" }
              }
            }
          ]
        }
      }
    }
  },
  "PollOptions": { "Timeout": 10000 }
}
```

Важно:

- нельзя передать `file.txt` as-is (нужен JSON `TSchemeOperation`);
- несколько `ModifyScheme` в файле = несколько запросов;
- при `INPROGRESS` нужен отдельный `SchemeOperationStatus` (CLI поллит сам);
- операция требует admin access.

---

## 3. Аналог `/viewer/json/describe?path={path}&partition_config=true` через gRPC

### Что делает viewer

Handler: `TJsonDescribe`  
Файл: `ydb/core/viewer/viewer_describe.h`  
Маршрут: `/viewer/describe` (исторически также `/viewer/json/describe`)

Viewer собирает `NKikimrSchemeOp::TDescribePath` и выставляет опции, включая:

```cpp
record.MutableOptions()->SetReturnPartitionConfig(
    FromStringWithDefault<bool>(Params.Get("partition_config"), true));
```

Далее запрос идёт в SchemeShard через TxProxy (`TEvTxUserProxy::TEvNavigate`) либо напрямую в tablet.  
Ответ — JSON от внутреннего `PathDescription` (включая `Table.PartitionConfig`).

### Legacy gRPC — ближайший аналог (почти 1:1)

```protobuf
// ydb/core/protos/grpc.proto
rpc SchemeDescribe(TSchemeDescribe) returns (TResponse);
```

Запрос:

```protobuf
// ydb/core/protos/msgbus.proto
message TSchemeDescribe {
  optional string Path = 1;
  optional uint64 PathId = 2;
  optional uint64 SchemeshardId = 3;
  optional string SecurityToken = 5;
  optional NKikimrSchemeOp.TDescribeOptions Options = 6;
}
```

`ReturnPartitionConfig` по умолчанию `true` в `TDescribeOptions`.

Серверный путь совпадает с viewer (SchemeShard describe):

```text
SchemeDescribe → MsgBusProxy FlatDescribe → TxProxy Navigate → SchemeShard
```

В ответе: `TResponse.PathDescription` — тот же raw internal protobuf, что использует viewer.

CLI-эквивалент:

```bash
ydbd -s grpcs://host:2135 --ca-file ca.crt --token-file ydb-token \
  db schema describe /Root/test/mytab1 -P
```

Пример смысла legacy-запроса:

```protobuf
Path: "/Root/test/mytab1"
Options {
  ReturnPartitionConfig: true
  ReturnPartitioningInfo: true
}
```

### Публичные gRPC

| API | Аналог viewer describe? | Комментарий |
|---|---|---|
| `Ydb.Scheme.DescribePath` | нет | только entry (имя/тип/ACL), без `PartitionConfig` |
| `Ydb.Table.DescribeTable` | частичный (только таблицы) | `PartitionConfig` конвертируется в public-модель |

Конвертация в `DescribeTable`:

| Internal (`PartitionConfig`) | Public (`DescribeTableResult`) |
|---|---|
| `ColumnFamilies[default].StorageConfig.SysLog` | `storage_settings.tablet_commit_log0.media` |
| `ColumnFamilies[default].StorageConfig.Log` | `storage_settings.tablet_commit_log1.media` |
| `ColumnFamilies[default].StorageConfig.Data` | `column_families[].data.media` |
| Прочие внутренние поля `PartitionConfig` | часто отсутствуют / теряются |

`DescribeTable` тоже ходит в `TDescribePath` и по умолчанию получает `ReturnPartitionConfig=true`, но отдаёт уже преобразованный public protobuf, а не raw `PathDescription`.

### Сводка по describe

| Цель | API |
|---|---|
| Тот же raw `PathDescription` / `PartitionConfig`, что у viewer | **legacy `SchemeDescribe`** |
| Публичный describe таблицы (storage media и т.п.) | `Ydb.Table.DescribeTable` |
| Только метаданные пути | `Ydb.Scheme.DescribePath` |

---

## 4. Итоговая таблица

| Операция | CLI / Viewer | Рабочий внешний API | HTTP на Embedded UI |
|---|---|---|---|
| Выполнить `ModifyScheme` из proto-файла | `ydbd db schema execute` | legacy gRPC `SchemeOperation` | `/CLI_MB/SchemeOperation` — **недоступен** в обычном `ydbd` |
| Describe с `PartitionConfig` | `/viewer/json/describe?...&partition_config=true` | legacy gRPC `SchemeDescribe` | viewer HTTP — да; MessageBus HTTP — нет |
| Describe таблицы в public API | — | `Ydb.Table.DescribeTable` | — |

### Практические рекомендации

1. Для автоматизации `schema execute` использовать **legacy gRPC `SchemeOperation`** (как CLI), а не HTTP Embedded UI.
2. Для parity с viewer describe использовать **legacy gRPC `SchemeDescribe`** с `Options.ReturnPartitionConfig=true`.
3. Public `DescribeTable` подходит, если достаточно `storage_settings` / `column_families`, а не полного internal `PartitionConfig`.
4. Не рассчитывать на `/CLI_MB/*` в production: MessageBus HTTP в текущем runner не активируется.
