# Распределенный планировщик заданий

![Архитектурная схема](architecture.svg)

## Назначение

Паттерн запускает задания по расписанию при нескольких экземплярах scheduler и пуле workers. Leader election упрощает диспетчеризацию, fencing token отсеивает устаревшего лидера, а транзакционная запись уникального `execution_id` является истинной защитой от повторного создания одного запуска.

## Когда применять

- расписаний больше, чем способен обслужить один процесс;
- требуется автоматический failover dispatcher;
- задания выполняются отдельным масштабируемым пулом;
- допустима at-least-once доставка при контролируемых повторах выполнения.

## Компоненты

- Row table **Schedules**, ключ `schedule_id`: правило, `next_run_at`, состояние и версия.
- Row table **SchedulerEpoch**, ключ `scheduler_name`: текущий монотонный epoch dispatcher.
- Row table **ExecutionLeases**, ключ `execution_id`: epoch, владелец, срок попытки и статус.
- Row table **ExecutionHistory**, ключ `(schedule_id, execution_id)`: запланированное время, попытки и итог.
- Row table **ExecutionOutbox**, ключ `execution_id`: payload задачи, epoch и состояние relay.
- Несколько **scheduler instances** сканируют сроки; выбранный dispatcher создает исполнения.
- **Coordination leader election** предоставляет только session-bound leader lease. Coordination не выдает epoch и не заменяет ACID.
- **Execution relay** читает changefeed `ExecutionOutbox`, ставит задачи в YMQ и выполняет recovery scan pending или зависших строк.
- **YMQ tasks** — отдельная SQS-совместимая очередь поверх YDB для competing consumers.
- **Workers** выполняют задания; committed-изменения `ExecutionHistory` поступают через CDC в **result Topic**, который является pub/sub.
- Политика retries повторно ставит временно неуспешные задачи, а исчерпанные попытки направляет в красный **DLQ**.

## Основной поток

1. Scheduler instances получают session-bound leader lease в Coordination; сам lease не содержит и не создает epoch.
2. Новый лидер отдельной ACID-транзакцией условно увеличивает строку `SchedulerEpoch` и использует возвращенное committed-значение как свой epoch.
3. Dispatcher читает наступившие строки `Schedules` и для каждого интервала детерминированно вычисляет `execution_id` из `schedule_id` и планового времени.
4. Одна условная транзакция проверяет равенство текущего `SchedulerEpoch`, резервирует уникальный `execution_id`, создает `ExecutionHistory`, `ExecutionLeases` и `ExecutionOutbox`, затем передвигает `next_run_at`.
5. CDC exactly-once записывает change record committed-вставки `ExecutionOutbox` в changefeed Topic. Relay идемпотентно ставит задачу в YMQ; recovery scan повторяет enqueue для pending или зависших строк.
6. Один из competing workers получает задачу и условно захватывает попытку в `ExecutionLeases`, проверяя `execution_id` и epoch.
7. Перед commit результата worker снова транзакционно проверяет `execution_id`, epoch и актуальную попытку, затем обновляет `ExecutionHistory`; CDC этой таблицы формирует change record для result Topic.
8. Временная ошибка приводит к retry с теми же `execution_id` и epoch; после лимита сообщение и контекст направляются в DLQ.

## Согласованность и надежность

Lease сам по себе не доказывает уникальность выполнения: пауза процесса или сетевое разделение оставляют старого worker активным. Истинная защита создания запуска — уникальная условная транзакционная запись `execution_id`. Epoch хранится в `SchedulerEpoch`, транзакционно увеличивается новым лидером и проверяется каждой записью dispatcher и каждым commit результата worker. Session-bound leader lease Coordination лишь определяет кандидата на лидерство.

Атомарная запись `ExecutionOutbox` устраняет окно между созданием execution, продвижением `next_run_at` и enqueue YMQ. Доставка YMQ и обработка результата рассматриваются как at-least-once. Обработчики и все внешние эффекты идемпотентны по `execution_id` и номеру шага. Coordination не заменяет ACID-транзакции YDB.

CDC exactly-once создает change record в changefeed Topic для каждого committed изменения исходной строки. При чтении или обработке relay/consumer возможен повтор, поэтому enqueue, результат и подписчики дедуплицируются по стабильному идентификатору.

## Масштабирование и ключи партиционирования

Расписания распределяются по `schedule_id`; для выборки сроков используется вычисляемый временной bucket с последующим подтверждением строки в транзакции. `ExecutionHistory` сохраняет `schedule_id` в ключе для истории конкретного расписания, а `ExecutionOutbox` распределяется по hash-prefix `execution_id`. При экстремально горячем расписании применяют hash-prefix исполнения. Relay и workers масштабируются независимо, YMQ распределяет задачи между competing consumers, а Topic обслуживает независимые consumer groups.

## Отказы и восстановление

- После потери session-bound lease Coordination выбирает нового лидера; новый лидер сам транзакционно увеличивает `SchedulerEpoch`, после чего записи старого epoch отклоняются.
- Commit мог пройти до тайм-аута: повтор с тем же `execution_id` обнаруживает существующую историю.
- Остановка relay после commit не теряет задачу: recovery scan находит `ExecutionOutbox`; сбой после enqueue создает допустимый дубликат.
- Worker может завершить внешний эффект и не записать результат; повтор исполнения возможен, поэтому эффект обязан быть идемпотентным.
- Истекший worker lease разрешает новую попытку, но не останавливает старый процесс; проверка `execution_id`, epoch и попытки отклоняет его commit.
- Недоступные подписчики дочитывают result Topic, а сообщения DLQ разбираются и переотправляются оператором после устранения причины.

## Ограничения и антипаттерны

- Нельзя считать leader lease или worker lease гарантией exactly-once.
- Нельзя генерировать случайный `execution_id` при каждом повторе одного планового интервала.
- Нельзя принимать запись от dispatcher без проверки epoch.
- Нельзя бесконечно повторять постоянную ошибку без лимита и DLQ.
- Решение не предназначено для DWH/OLAP и реляционной аналитики; column tables и YDB External Data Source не используются.
