# Интеграционный событийный хаб

![Архитектурная схема](architecture.svg)

## Назначение

Паттерн связывает системы через управляемый событийный контур: входные сообщения проверяются и нормализуются, каноническое состояние и статус доставки фиксируются в YDB, затем события или команды передаются целевым системам. Он отделяет форматы источников от контрактов получателей и делает повторы наблюдаемыми.

## Когда применять

- несколько систем обмениваются событиями и командами с разными контрактами;
- нужна единая валидация, версионирование схем и карантин;
- необходимо отслеживать прием, преобразование и доставку каждого сообщения;
- изменения row tables должны публиковаться через CDC.

## Компоненты

- Исходные и целевые **системы** подключаются только через app API, producers и consumers.
- **Incoming Topics** принимают события по Kafka API; Topic — pub/sub с независимыми consumer groups.
- **Validator/Normalizer** проверяет envelope и версию схемы, затем преобразует payload в канонический контракт.
- Row table **SchemaRegistry**, ключ `(schema_id, schema_version)`: контракт, состояние версии и policy совместимости.
- Row table **Inbox**, ключ `(source_id, message_id)`: дедупликация, версия схемы и результат проверки.
- Row table **CanonicalState**, ключ `(entity_type, entity_id)`: актуальная каноническая версия сущности.
- Row table **DeliveryStatus**, ключ `(message_id, destination_id)`: состояние, попытка и последняя ошибка.
- Row table **DeliveryOutbox/DispatchIntent**, ключ `(message_id, destination_id)`: тип маршрута `TOPIC` или `YMQ`, payload, стабильный event/command id и состояние relay.
- **Outgoing Topics** доставляют события подписчикам по модели pub/sub.
- **YMQ commands** — отдельная SQS-совместимая очередь поверх YDB для competing consumers, выполняющих адресные команды.
- **CDC/relay** читает changefeeds, публикует намерения доставки и выполняет recovery scan pending или зависших `DispatchIntent`.
- **CDC CanonicalState** напрямую образует outgoing changefeed Topic, когда источником события является изменение row table.
- **Quarantine/DLQ** хранит невалидные сообщения и доставки, исчерпавшие повторы.
- **Schema Registry/Policy** управляет поддерживаемыми версиями и правилами совместимости.

## Основной поток

1. Producer исходной системы отправляет envelope с `source_id`, `message_id`, `schema_id` и `schema_version` во входной Topic через Kafka API или service endpoint.
2. Validator читает policy из `SchemaRegistry` и проверяет контракт. Неизвестная версия или невалидный payload направляются в quarantine с причиной.
3. Normalizer одной ACID-транзакцией условно создает `Inbox`, обновляет `CanonicalState` и атомарно записывает `DeliveryStatus` вместе с `DeliveryOutbox/DispatchIntent`; повторный `message_id` возвращает сохраненный результат.
4. Для событий, источником которых является изменение `CanonicalState`, CDC exactly-once записывает change record в outgoing changefeed Topic. Путь идет напрямую `CanonicalState → CDC → Outgoing Topics`, без YMQ и DLQ.
5. Для явных адресных маршрутов CDC exactly-once записывает change record committed-вставки `DispatchIntent`; relay идемпотентно публикует событие в заданный outgoing Topic либо ставит команду в YMQ.
6. Независимые consumers читают Topic, а competing consumers разбирают YMQ; каждый получатель идемпотентно применяет сообщение.
7. Результат адресной доставки условно записывается в `DeliveryStatus`; временная ошибка повторяется, постоянная или исчерпавшая лимит попадает в DLQ соответствующего маршрута.
8. Recovery scan relay периодически находит pending или зависшие `DispatchIntent` и повторяет publish/enqueue с тем же event/command id.

## Согласованность и надежность

Транзакция YDB атомарно связывает дедупликацию Inbox, изменение канонического состояния, статус и `DispatchIntent`; это устраняет dual-write между commit состояния и publish/enqueue. Coordination при необходимости координирует краткие служебные операции, но не заменяет ACID. Topics и YMQ допускают повторную доставку; все consumers и внешние эффекты идемпотентны по `(source_id, message_id, destination_id)`.

CDC exactly-once создает change record в changefeed Topic для каждого committed изменения исходной строки. Повтор возможен при чтении или обработке record после сбоя; relay и consumers используют стабильный event/command id. Exactly-once change record не означает exactly-once внешний эффект.

Версия схемы находится в envelope, проверяется по `SchemaRegistry` и сохраняется в Inbox. Изменения контракта проходят policy совместимости; миграции normalizer поддерживают ограниченное окно версий. Ошибка отдельного получателя не блокирует остальных.

## Масштабирование и ключи партиционирования

Incoming и outgoing Topics партиционируются по стабильному `entity_id`, когда важен порядок сущности, либо по `message_id`, когда важнее равномерность. `Inbox` распределяется по `source_id` и hash-prefix `message_id`; `CanonicalState` — по типу и идентификатору сущности; `DeliveryStatus` и `DispatchIntent` — по hash-prefix сообщения и получателю. Validator, normalizer, relay и consumers масштабируются горизонтально своими consumer groups; YMQ распределяет команды между competing consumers.

## Отказы и восстановление

- Повтор входного сообщения обнаруживается по ключу Inbox и не создает второе изменение состояния.
- После commit до подтверждения consumer перечитывает сообщение и продолжает по сохраненному статусу.
- Остановка relay после commit не теряет намерение: changefeed сохраняет record, а recovery scan находит pending `DispatchIntent`.
- Сбой relay после publish/enqueue, но до отметки строки создает допустимый дубликат с тем же идентификатором.
- Неизвестная схема остается в quarantine до добавления безопасного преобразования и контролируемого replay.
- Недоступный получатель восстанавливает чтение Topic со своей позиции или получает повтор YMQ.
- DLQ сохраняет исходный envelope, назначение и диагностику; replay выполняется с тем же идентификатором после исправления причины.

## Ограничения и антипаттерны

- Интеграция выполняется только через SDK, Kafka API и service endpoints. **YDB External Data Source явно не используется.**
- Нельзя давать системам прямой доступ к внутренним таблицам друг друга.
- Нельзя менять смысл существующей версии схемы или терять исходный `message_id`.
- Нельзя полагаться на exactly-once доставку вместо идемпотентности получателя.
- Хаб не является DWH/OLAP и средством реляционной аналитики; column tables не используются.
