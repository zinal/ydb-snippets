# CQRS с CDC и версионируемыми проекциями
![Архитектурная схема](architecture.svg)

## Назначение
CQRS разделяет модель записи и модели чтения. Command API проверяет инварианты и изменяет нормализованные строковые таблицы YDB; CDC ровно один раз записывает change record каждого committed change в changefeed topic, а независимые projectors строят денормализованные строковые read models для Query API. YDB Topics здесь — replayable pub/sub log с consumer groups, а не очередь competing consumers.

## Когда применять
- Профиль записи и набор запросов существенно различаются.
- Для чтения нужны несколько представлений с независимым масштабированием и жизненным циклом.
- Допустима явно измеряемая eventual consistency между подтверждением команды и появлением данных в Query API.
- Нужны безопасный rebuild и переключение версии проекции без остановки записи.

## Компоненты
- **Command API / handler**: принимает `command_id`, проверяет бизнес-инварианты и выполняет ACID-транзакцию.
- **Write model**: нормализованные строковые таблицы `Customers` (`customer_id`), `Orders` (`order_id`), `OrderLines` (`order_id`, `line_no`) и результаты идемпотентных команд `CommandResults` (`command_id`).
- **CDC/changefeed**: для каждого committed change ровно один раз записывает change record в YDB Topic `orders.changefeed`; это partitioned pub/sub log. Повтор возможен при чтении или обработке subscriber, но не при создании CDC-записи.
- **Projectors**: consumer groups `orders-summary-v1`, `orders-by-customer-v1` и временная `orders-summary-v2-rebuild`.
- **Read models**: строковые таблицы `OrderSummary_v1` (`order_id`), `OrdersByCustomer_v1` (`customer_id`, `updated_bucket`, `order_id`) и новая `OrderSummary_v2`.
- **Прогресс и дедупликация**: встроенный consumer offset YDB Topic коммитится транзакционно вместе с read model. `ProjectionOffsets` (`projection_name`, `partition_id`) хранит версию projector и диагностический lag, но не служит вторым resume-offset; `ProcessedEvents` (`projection_name`, `event_id`) защищает replay и внешние эффекты.
- **Query API**: читает только активную версию read model; указатель хранится в `ProjectionRegistry` (`projection_name`).
- **Coordination**: lease rebuild-воркера и сериализация переключения версии; Coordination не заменяет ACID.

## Основной поток
1. Клиент отправляет команду с `command_id` в Command API.
2. Handler читает нужную версию write model, проверяет инварианты и в одной YDB ACID-транзакции изменяет `Orders`/`OrderLines` и сохраняет результат в `CommandResults`; повтор `command_id` возвращает тот же результат.
3. CDC получает только committed changes и ровно один раз записывает для каждого из них change record со стабильным `event_id` в `orders.changefeed`, используя `order_id` как partition key.
4. Каждый projector читает topic в своей consumer group. В одной YDB topic+table транзакции он изменяет свою строковую read model и `ProcessedEvents`, затем транзакционно коммитит встроенный consumer offset. При rollback не фиксируются ни модель, ни offset; повтор чтения безопасен.
5. Query API читает активную таблицу, указанную в `ProjectionRegistry`; сразу после шага 2 старая версия ответа еще допустима — это eventual consistency.
6. Для rebuild создаются новая строковая read model `OrderSummary_v2` и отдельная consumer group `orders-summary-v2-rebuild`. Согласованный snapshot/baseline write tables привязывается к позиции changefeed, после чего новая group догоняет live-поток до контрольного встроенного consumer offset.
7. После проверки полноты и lag `ProjectionRegistry` атомарно переключает Query API с `OrderSummary_v1` на `OrderSummary_v2`; v1 сохраняется для быстрого rollback и удаляется позже по регламенту.
8. Любые внешние эффекты projector выполняет идемпотентно по `event_id`; предпочтительно отделять их от построения проекции.

## Согласованность и надежность
Write model имеет строгую согласованность в рамках ACID-транзакции, read models — eventual consistency. Контракт API должен сообщать клиенту `write_version` или состояние «обновляется», если требуется read-your-writes. CDC ровно один раз создает change record в changefeed topic; subscriber может повторно прочитать или начать обработку записи после сбоя. Topic+table транзакция атомарно фиксирует изменение read model и встроенный consumer offset, а `ProcessedEvents` и идемпотентные внешние эффекты защищают replay и побочные действия. Coordination управляет владением работой, но не обеспечивает атомарность таблиц. YMQ/SQS-подобная очередь, если она добавляется для служебных команд, является отдельным сервисом поверх YDB с competing consumers, а не встроенным объектом YDB.

## Масштабирование и ключи партиционирования
`orders.changefeed` партиционируется по `order_id`, сохраняя порядок изменений заказа. `OrdersByCustomer_v1` распределяет горячих клиентов дополнительным `updated_bucket`; запрос объединяет ограниченное число bucket. Встроенный consumer offset ведется отдельно для каждой partition consumer group; диагностические строки `ProjectionOffsets` также разделены по `partition_id` и не участвуют в resume-протоколе. Число экземпляров projector ограничено числом партиций его consumer group, а Query API масштабируется независимо.

## Отказы и восстановление
- При падении projector продолжает со встроенного consumer offset своей YDB Topic consumer group. Незакоммиченный batch читается снова; topic+table транзакция не оставляет частично обновленную read model, а `ProcessedEvents` защищает контролируемый replay.
- Poison event переводит конкретную проекцию в состояние `blocked`, сохраняется с диагностикой и исправляется контролируемым replay; тихо пропускать событие нельзя.
- При длительном простое выполняется rebuild новой версии из write model и changefeed, а не изменение активной таблицы на месте.
- Если v2 не догнала контрольный offset или не прошла сверку, переключение не выполняется; активной остается v1.
- Неопределенный результат команды повторяется с тем же `command_id`; внешние вызовы — только с идемпотентным ключом.

## Ограничения и антипаттерны
- Нельзя писать через Query API или изменять read model вручную как источник истины.
- Нельзя коммитить встроенный consumer offset отдельно от транзакционного обновления проекции; `ProjectionOffsets` нельзя использовать как конкурирующий resume-механизм.
- Нельзя обещать мгновенную согласованность после команды без отдельного протокола read-your-writes.
- Нельзя перестраивать активную таблицу in-place: используйте новую версию и атомарное переключение.
- Нельзя выбирать глобальный partition key, нарушающий порядок одного `order_id` или создающий hot partition.
- Нельзя считать Coordination заменой ACID, Topic — очередью competing consumers, а retention topic — бессрочным архивом данных.
