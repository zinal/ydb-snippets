# Долгоживущий workflow и Saga в YDB

![Архитектурная схема](architecture.svg)

## Назначение

Архитектура реализует оркестрируемую Saga: конечный автомат хранит состояние долгоживущего workflow, выдает идемпотентные команды, принимает результаты, запускает таймеры и выполняет компенсации. YDB хранит только строковые таблицы операционного состояния.

## Когда применять

- бизнес-процесс состоит из нескольких локальных транзакций и внешних side effects;
- процесс живет дольше одного запроса и должен восстанавливаться после перезапуска;
- нужны таймеры, retry, компенсации и ручное разрешение неоднозначного результата;
- шаги допускают идемпотентное исполнение или проверку ранее полученного результата.

Saga не создает распределенную ACID-транзакцию: промежуточные состояния видимы, а компенсация является отдельным бизнес-действием и тоже может завершиться ошибкой.

## Компоненты

| Компонент | Роль |
|---|---|
| API / Orchestrator | Внешнее приложение конечного автомата, проверяющее версию workflow и выбирающее следующий шаг |
| WorkflowInstances | Строковая таблица состояния, версии и результата экземпляра; ключ `workflow_id` |
| Steps | Строковая таблица попыток и результатов шагов; ключ начинается с `workflow_id` |
| Timers | Строковая таблица дедлайнов; ключ распределяет bucket времени и включает `workflow_id` |
| CommandOutbox | Строковая таблица команд, атомарно записанных с переходом состояния |
| Inbox | Строковая таблица дедупликации результатов и входных сообщений |
| DispatcherEpoch / TimerDispatchLease | Строковая таблица монотонного epoch и lease таймеров; именно она является источником fencing epoch |
| Timer dispatcher | Внешнее приложение: сканирует/claim наступившие таймеры и транзакционно записывает ack/переход |
| Coordination | Только session-bound leader lease; Coordination не создает монотонный fencing token |
| SQS queue | Встроенная реализация SQS-совместимого протокола, доступная во всех поддерживаемых развертываниях YDB: competing consumers, visibility timeout, ack/delete и retry |
| Workers | Внешние competing consumers выполняют обычные и компенсационные команды |
| Result Topic | YDB Topic результатов; publisher задает `producer_id = message_group_id = workflow_id` |
| Result consumer | Внешний именованный YDB Consumer передает результаты оркестратору |
| DLQ | Изолирует команды после исчерпания retry для ручного разбора |

Встроенная SQS queue предоставляет competing consumers, visibility timeout, ack/delete, retry и DLQ. YDB Topics — другая модель: долговечный pub/sub log с именованными YDB Consumers. Результаты публикуются в Topic, а не трактуются как сообщения той же очереди. Нахождение SQS queue внутри границы YDB не включает enqueue/ack в ACID-транзакцию row tables.

Внутри границы YDB находятся row tables, Result Topic, changefeed/CDC при использовании, Coordination, SQS queue и DLQ. API, orchestrator, outbox relay, timer dispatcher, command workers и result consumer — внешние приложения.

## Основной поток

1. API создает `WorkflowInstances` и начальный `Steps`, а в той же ACID-транзакции добавляет команду в `CommandOutbox`.
2. Внешний outbox relay асинхронно переносит committed `CommandOutbox` change record во встроенную SQS queue; повторная отправка безопасна благодаря стабильному `command_id`. Row-table transaction и enqueue в SQS не атомарны.
3. Один из competing workers получает команду, выполняет идемпотентный внешний side effect и публикует результат в Result Topic с `producer_id = message_group_id = workflow_id`. После подтвержденной записи результата worker выполняет SQS ack/delete; сбой до ack приводит к повторной доставке.
4. Внешний result consumer читает Topic через именованный YDB Consumer и передает результат orchestrator. Тот дедуплицирует `message_id` в `Inbox` и в одной транзакции обновляет `Steps`, версию `WorkflowInstances`, необходимые `Timers` и следующую `CommandOutbox`.
5. При успехе автомат переходит к следующему шагу или завершает workflow.
6. При окончательной ошибке автомат в обратном порядке создает команды компенсации для уже выполненных шагов.
7. Новый лидер получает session-bound lease в Coordination, затем в транзакции YDB увеличивает `DispatcherEpoch` и запоминает полученный epoch. Coordination сама epoch не выдает.
8. Внешний timer dispatcher сканирует due-диапазон `Timers`, транзакционно claim-запись в `TimerDispatchLease` с текущим epoch, а после dispatch записывает ack/переход обратно в YDB. Каждая команда таймера несет epoch, а worker и транзакция записи сверяют его с текущим `DispatcherEpoch`; устаревший лидер не может зафиксировать переход.
9. После исчерпания retry команда отправляется в DLQ; оператор сверяет внешний результат и явно возобновляет, компенсирует либо завершает процесс вручную.

## Согласованность и надежность

Переход конечного автомата, версия экземпляра, шаг, таймер и outbox-запись фиксируются одной ACID-транзакцией YDB. Optimistic concurrency по версии не позволяет двум результатам одновременно продвинуть Saga. Inbox делает повторную доставку результата безвредной.

SQS queue и Result Topic работают асинхронно и дают доставку как минимум один раз на прикладной границе. Visibility timeout не означает отмену уже начатого вызова. Каждый внешний side effect и компенсация обязаны принимать idempotency key (`command_id`) либо уметь надежно обнаруживать ранее выполненную операцию.

Coordination не заменяет ACID и предоставляет только lease, привязанный к сессии. Монотонный fencing epoch создается транзакционным увеличением `DispatcherEpoch` в строковой таблице YDB; `TimerDispatchLease`, workers и все записи переходов проверяют этот epoch. Потеря сессии не мгновенно останавливает старый процесс, но сравнение epoch не дает ему зафиксировать состояние. Если timer worker делает внешний side effect, внешняя система должна проверять epoch либо операция должна быть идемпотентной.

Если relay для `CommandOutbox` использует CDC, CDC создает одну change record на каждое committed row change. Чтение, доставка и обработка record могут повторяться, поэтому `command_id` остается обязательным; exactly-once processing не обещается.

## Масштабирование и ключи партиционирования

`workflow_id` остается в PK таблиц `WorkflowInstances`, `Steps`, `CommandOutbox` и `Inbox`. Если требуется hash-sharding, хеш служит только shard prefix: `(hash(workflow_id) % N, workflow_id, ...)`; исходный `workflow_id` не заменяется хешем. SQS queue масштабирует workers как competing consumers. Для Result Topic используется `producer_id = message_group_id = workflow_id`, поэтому порядок результатов одного процесса сохраняется внутри `producer_id`; result consumer — именованный YDB Consumer.

Для `Timers` нельзя использовать голый монотонный timestamp первым ключом: применяются временной bucket и shard prefix, например `(bucket, hash(workflow_id) % N, deadline, workflow_id)`. Хеш только распределяет shard, исходный `workflow_id` остается в PK. Несколько dispatcher-процессов могут обслуживать разные buckets, а Coordination выдает только session-bound leader lease там, где требуется эксклюзивное назначение. `DispatcherEpoch` отдельно создает монотонный epoch транзакцией row table и является редкой точкой записи при смене лидера.

## Отказы и восстановление

После commit, но до отправки publisher повторно прочитает `CommandOutbox`. Дубликат команды безопасен по `command_id`. Если worker завершил side effect и упал до результата, команда появится после visibility timeout; повтор обязан вернуть прежний результат. Просроченная Coordination-сессия приводит к перевыборам; новый лидер транзакционно увеличивает `DispatcherEpoch`, и проверки epoch отклоняют записи старого лидера.

Команды с постоянной ошибкой после backoff попадают в DLQ. Неоднозначный внешний результат, провал компенсации или несовместимое изменение схемы процесса требуют ручного вмешательства; оператор не должен слепо повторять неидемпотентную операцию.

## Ограничения и антипаттерны

- Считать Saga эквивалентом распределенной ACID-транзакции.
- Хранить состояние автомата только в памяти оркестратора.
- Публиковать команду отдельно от перехода без outbox.
- Считать visibility timeout гарантией exactly-once или отменой side effect.
- Выполнять внешний side effect без idempotency key.
- Считать Coordination источником монотонного token или полагаться на leader election без `DispatcherEpoch` и проверки сессии.
- Считать компенсацию техническим rollback либо путать SQS queue с Topics.
