# Event-driven микросервисы: транзакционная публикация и Outbox
![Архитектурная схема](architecture.svg)

## Назначение
Архитектура связывает bounded context «Заказы», «Платежи» и «Доставка» событиями, не открывая сервисам прямой доступ к чужим таблицам. Каждый сервис владеет своими строковыми таблицами YDB и публикует факты через YDB Topics — журнал pub/sub. Для команд, отложенных повторов и распределения одной задачи между исполнителями используется YMQ/SQS-подобная очередь с competing consumers: это отдельный сервис поверх YDB, а не встроенный объект YDB.

## Когда применять
- Бизнес-операция затрагивает несколько автономных сервисов, а распределенная транзакция нежелательна.
- Нужна надежная публикация события вместе с изменением состояния.
- Допустима eventual consistency между bounded context и нужны повторная доставка и независимо масштабируемые подписчики.
- Требуется выбирать между прямой транзакционной публикацией и классическим Outbox без изменения бизнес-контракта события.

## Компоненты
- **Orders Service**: строковые таблицы `Orders` (`order_id`) и `OrderItems` (`order_id`, `line_no`).
- **Payments Service**: строковые таблицы `Payments` (`payment_id`) и `PaymentByOrder` (`order_id`).
- **Delivery Service**: строковые таблицы `Shipments` (`shipment_id`) и `ShipmentByOrder` (`order_id`).
- **YDB Topics**: `orders.events`, `payments.events`, `delivery.events`; это partitioned pub/sub log, а не очередь competing consumers. Для пользовательской записи задается `producer_id = message_group_id = order_id`; порядок сохраняется внутри `producer_id`.
- **Классический Outbox**: строковая таблица `OrderOutbox` (`shard_prefix`, `created_at`, `event_id`), CDC/changefeed и отдельный Outbox Relay вне границы YDB. `shard_prefix = hash(event_id) % N` только распределяет нагрузку, а исходный `event_id` обязательно остается в полном PK: hash-only identity запрещена. CDC создает ровно одну change record для каждого committed row change; чтение и обработка relay могут повториться.
- **Inbox/Deduplication** каждого consumer: строковые таблицы `PaymentInbox` и `DeliveryInbox` с ключом `event_id`.
- **Командная очередь и DLQ**: `payment.commands`, `delivery.retry`, `delivery.dlq` в отдельном YMQ/SQS-подобном сервисе поверх YDB.
- **YDB Consumers**: именованные `YDB Consumer payments` и `YDB Consumer delivery`; offset каждого consumer хранится отдельно по партициям Topic.
- **Coordination**: опциональные lease и выбор лидера для relay/воркеров; Coordination не заменяет ACID-транзакции.

## Основной поток
1. Клиент отправляет команду в Orders Service; сервис изменяет `Orders` и `OrderItems`.
2. Selector выбирает ровно один путь для типа события: **A XOR B**. Вариант A — одна `table + Topic transaction`, изменяющая `Orders`/`OrderItems` и публикующая `OrderCreated` в `orders.events`.
3. Вариант B — одна транзакция `table + Outbox`; CDC создает ровно одну change record committed row change в внутреннем changefeed без пользовательских `producer_id`/`message_group_id`. Внешний Outbox Relay читает ее, публикует событие в `orders.events` и затем коммитит offset. Повтор между publish и offset commit сохраняет тот же `event_id`. A и B никогда не применяются одновременно к одному типу события.
4. `YDB Consumer payments` и `YDB Consumer delivery` независимо читают `orders.events`. Каждый consumer атомарно фиксирует `event_id` в своей Inbox/Deduplication и обновляет только собственные таблицы.
5. Payments Service публикует `PaymentAuthorized` в `payments.events` с `producer_id = message_group_id = order_id`; Delivery Service читает его через именованный `YDB Consumer delivery-payments`.
6. Команды и контролируемые повторы попадают в YMQ-подобную очередь, где одну запись забирает один из competing consumers; исчерпавшие лимит сообщения переходят в DLQ.
7. Внешние эффекты — списание у провайдера, письмо, вызов перевозчика — выполняются идемпотентно по `event_id` или отдельному `idempotency_key`.

## Согласованность и надежность
Внутри сервиса состояние и выбранный путь публикации согласованы ACID. Между сервисами действует eventual consistency и обработка подписчиком как минимум один раз, поэтому Inbox/Deduplication обязательна. CDC создает ровно одну change record на committed row change; дубликат доменного события возможен при повторной обработке relay или subscriber. Пользовательский Topic сохраняет порядок внутри `producer_id`, а offset именованного YDB Consumer хранится по партициям и не подтверждает внешний эффект. Coordination помогает владеть lease, но не обеспечивает атомарность данных и сообщения.

## Масштабирование и ключи партиционирования
Для пользовательских Topics применяется `producer_id = message_group_id = order_id`, поэтому события заказа упорядочены внутри этого producer. `payment_id` и `shipment_id` распределяют основные таблицы. У монотонного времени `OrderOutbox` использует `shard_prefix` перед временем, но полный PK также содержит исходный `event_id`. Именованный YDB Consumer масштабируется числом партиций Topic, а competing consumers YMQ — числом воркеров очереди.

## Отказы и восстановление
- После неопределенного результата коммита команда повторяется с тем же `idempotency_key`; сервис читает сохраненный результат.
- Упавший именованный YDB Consumer продолжает с offset своей партиции, а Inbox отсекает повтор.
- Outbox relay продолжает с подтвержденного offset changefeed topic; если publish завершился до сбоя, повторная обработка может снова опубликовать событие с тем же `event_id`.
- Временные ошибки команд обрабатываются backoff-повторами, постоянные — DLQ с ручным разбором и контролируемым redrive.
- Если внешний вызов завершился, а подтверждение потеряно, повтор безопасен только при поддержке идемпотентного ключа внешней системой.

## Ограничения и антипаттерны
- Нельзя читать или изменять таблицы другого bounded context: интеграция идет через контракт API/события.
- Нельзя выполнять «сначала запись, потом publish» двумя несвязанными операциями: сбой потеряет событие.
- Нельзя считать scoped-гарантию CDC заменой идемпотентной бизнес-обработки subscriber и внешних эффектов.
- Нельзя использовать один глобальный ключ партиционирования или один relay для всего потока.
- Нельзя называть YMQ встроенной очередью YDB или подменять очередью replayable pub/sub log.
- Нельзя использовать Coordination как распределенную ACID-транзакцию.
