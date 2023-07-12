# Задержки простейшего запроса

Текст запроса:
```
DECLARE $p AS Int32; SELECT $p AS out;
```

Условия выполнения: по N штук на транзакцию SerializableRW, N=3..9, без задержек, последовательно.

Результаты для Golang, YDB Go SDK v3.48.5

| Среда | Средняя задержка на 1 запрос, мсек |
| ----- | ---------------------------------- |
| YDB Serverless, SingleConn | 20.733 |
| YDB Dedicated, default endpoint | 3.523 |
| YDB Dedicated, same DC vm, SingleConn | 1.405 |
| YDB Self-hosted, same DC, 3 nodes | 0.807 |
| YDB Local, same host | 0.451 |
