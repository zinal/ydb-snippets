# Event Sourcing на строковых таблицах YDB
![Архитектурная схема](architecture.svg)

## Назначение
Состояние агрегата восстанавливается из неизменяемой последовательности доменных событий в долговечной строковой таблице `EventLog`. Это источник истины; YDB Topic используется как pub/sub log для оперативной доставки событий projectors, но его ограниченный retention не должен быть единственным долговечным источником. Текущее состояние для запросов хранится в производных строковых read models.

## Когда применять
- История изменений имеет самостоятельную бизнес-ценность и нужна детерминированная реконструкция состояния.
- Правила удобно выражаются через aggregate и optimistic concurrency.
- Нужны независимые проекции, аудит и возможность построить новую модель чтения replay событий.
- Команда может принять дополнительную сложность схем событий, миграций, replay и eventual consistency.

## Компоненты
- **Command API / Aggregate Handler вне YDB**: принимает `command_id`, загружает aggregate и ожидаемую версию, проверяет инварианты.
- **`EventLog`**: долговечная строковая таблица с ключом (`aggregate_id`, `aggregate_version`), содержащая `event_id`, `event_type`, payload и время.
- **`AggregateHeads`**: строковая таблица (`aggregate_id`) с текущей версией для optimistic compare-and-set.
- **`AggregateSnapshots`**: необязательная строковая таблица (`aggregate_id`, `snapshot_version`) для ускорения загрузки; это кэш, не источник истины.
- **`IdempotencyKeys`**: строковая таблица (`command_id`) с результатом команды и диапазоном созданных событий.
- **Пользовательский Topic `domain.events`**: YDB Topics = partitioned pub/sub log; writer задает `producer_id = message_group_id = aggregate_id`, и порядок сохраняется внутри `producer_id`.
- **Альтернатива CDC**: внутренний `eventlog.changefeed` принадлежит только `EventLog`, создает ровно одну change record на committed row change и не получает произвольные пользовательские writer IDs.
- **Projectors и replay workers вне YDB**: именованные `YDB Consumer order-state-live`, `YDB Consumer orders-by-customer-live` и `YDB Consumer projection-v2-rebuild` строят строковые read models `OrderState` (`aggregate_id`) и `OrdersByCustomer` (`customer_id`, `bucket`, `aggregate_id`).
- **Offsets и дедупликация**: встроенный consumer offset коммитится в topic+table транзакции вместе с read model. `ProjectionOffsets` хранит версию projector и диагностический lag, но не является вторым resume-offset; `ProcessedEvents` использует полный ключ (`projection_name`, `source`, `aggregate_id`, `aggregate_version`).
- **Coordination**: lease projector/replay worker; Coordination не заменяет ACID.

## Основной поток
1. Command API получает команду с `command_id`, `aggregate_id` и `expected_version`.
2. Handler проверяет `IdempotencyKeys`; при первом вызове читает snapshot и хвост `EventLog`, затем восстанавливает aggregate и проверяет инварианты.
3. В предпочтительном варианте одна YDB ACID-транзакция условно обновляет `AggregateHeads`, добавляет события в `EventLog`, сохраняет `IdempotencyKeys` и публикует их в `domain.events` с `producer_id = message_group_id = aggregate_id`.
4. В альтернативном варианте транзакция пишет `EventLog`, а CDC создает ровно одну change record на committed row change во внутреннем `eventlog.changefeed`; пользовательские writer IDs к нему неприменимы. Варианты не применяются одновременно к одному событию, а чтение/обработка subscriber в обоих случаях могут повториться.
5. Конкурирующая команда с устаревшей версией получает conflict, перечитывает aggregate и повторно принимает бизнес-решение, а не слепо повторяет запись.
6. Внешний projector читает выбранный источник через именованный YDB Consumer. Для `domain.events` порядок идет внутри `producer_id = aggregate_id`; для CDC identity и порядок задает полный PK `EventLog`. В одной topic+table транзакции projector обновляет read model и `ProcessedEvents`, затем коммитит встроенный consumer offset по партициям.
7. Query API читает только read models; между commit события и обновлением проекции действует явная eventual consistency.
8. Snapshot создается после заданного числа событий и проверяется по `snapshot_version`; aggregate всегда может быть восстановлен из `EventLog` без snapshot.
9. Внешние эффекты выполняются идемпотентно по (`source`, `aggregate_id`, `aggregate_version`) либо `command_id`, поскольку чтение и replay допускают повторы.

## Согласованность и надежность
Добавление событий, смена aggregate version, запись idempotency result и предпочтительная публикация атомарны. В альтернативе CDC создает ровно одну change record на committed row change; чтение и обработка могут повториться. Topic+table транзакция атомарно фиксирует read model и встроенный consumer offset по партициям, а полный ключ `ProcessedEvents` и идемпотентность защищают replay и внешние эффекты. `domain.events` сохраняет порядок внутри `producer_id = aggregate_id`; глобального порядка нет. Topic retention не является источником истины: полная долговечная история остается в `EventLog`. Coordination распределяет lease, но не добавляет транзакционность.

Встроенная в YDB реализация SQS-совместимого протокола может опционально применяться для команд и ограниченных повторов. SQS queues используют competing consumers, visibility timeout, ack/delete, retries и DLQ; это deployment-neutral механизм, не замена `EventLog` или YDB Topic. Атомарность row table + SQS enqueue не предполагается: если enqueue должен быть связан с записью, нужен Outbox/CDC/relay.

## Масштабирование и ключи партиционирования
`EventLog` использует полный PK (`aggregate_id`, `aggregate_version`). Пользовательский Topic использует `producer_id = message_group_id = aggregate_id`; внутренний CDC Topic не получает произвольный producer. Aggregate с экстремальной частотой команд требует изменения границ агрегата. Если `bucket` read model вычисляется hash-функцией, полный PK сохраняет исходные `customer_id` и `aggregate_id`: hash-only identity запрещена. Встроенный consumer offset ведется по партициям именованного YDB Consumer; `ProjectionOffsets` не участвует в resume-протоколе.

## Отказы и восстановление
- Неопределенный результат commit проверяется повтором того же `command_id`; `IdempotencyKeys` возвращает исходный результат без новых событий.
- Version conflict не является инфраструктурным повтором: aggregate перечитывается, команда валидируется заново.
- Упавший projector продолжает со встроенного offset по партициям своего именованного YDB Consumer. Незакоммиченный batch читается снова; topic+table транзакция не оставляет частично обновленную read model.
- Утерянная проекция строится внешним replay worker в новой таблице из полного `EventLog`, затем отдельный `YDB Consumer projection-v2-rebuild` догоняет live-поток и выполняется атомарное переключение.
- Невалидный snapshot отбрасывается; восстановление продолжается из событий.
- Poison event останавливает затронутую проекцию до исправления обработчика/upcaster; событие нельзя тихо пропускать.

## Ограничения и антипаттерны
- Нельзя использовать topic retention как единственное долговечное хранилище событий.
- Нельзя изменять или удалять опубликованные строки `EventLog`; исправление оформляется компенсирующим событием.
- Нельзя менять смысл старого `event_type` без версий схемы и детерминированных upcaster.
- Нельзя считать snapshot источником истины или строить его в той же горячей транзакции после каждой команды.
- Нельзя сохранять в событии недетерминированные ссылки на текущее внешнее состояние.
- Нельзя обещать глобальный порядок, однократность внешних эффектов или мгновенную согласованность read model.
- Нельзя коммитить consumer offset отдельно от read model или использовать `ProjectionOffsets` как конкурирующий resume-механизм.
- Нельзя использовать Coordination вместо ACID или давать Query API прямую запись в проекцию.
