# Задержки простейшего запроса

Текст запроса:

```yql
DECLARE $p AS Int32; SELECT 1+$p AS out;
```

Условия выполнения: по N штук на транзакцию SerializableRW, N=3..9, без задержек, последовательно.

Значения параметра случайные, на выходе контролируется результат на соответствие `вход+1 = выход`.

## Результаты для Golang

YDB Go SDK v3.48.5 (native)

| Среда | Средняя задержка на 1 запрос, мсек |
| ----- | ---------------------------------- |
| YDB Serverless, SingleConn | 20.733 |
| YDB Dedicated, default endpoint | 3.523 |
| YDB Dedicated, same DC endpoint, SingleConn | 1.405 |
| YDB Self-hosted, same DC, 3 nodes | 0.807 |
| YDB Local, same host | 0.451 |

> SingleConn - принудительное выключение клиентской балансировки.

## Результаты для Python

YDB Python SDK v3.3.6

| Среда | Средняя задержка на 1 запрос, мсек |
| ----- | ---------------------------------- |
| YDB Serverless | 22.773 |
| YDB Dedicated, default endpoint | 1.7347 |
| YDB Dedicated, same DC vm | 1.7215 |
| YDB Self-hosted, same DC, 3 nodes | 1.0321 |
| YDB Local, same host | 0.6733 |
