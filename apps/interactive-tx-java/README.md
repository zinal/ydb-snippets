Пример реализации интерактивной транзакции с использованием Table Service.

Для сборки и запуска требуется JDK 17+ и Maven.

Параметры подключения к БД прописываются в `interactive-tx-config.xml`.

При успешном выполнении рабочие таблички и схема удаляются.

```bash
mvn clean package
ydb scheme rmdir -r interactive-tx
mvn exec:java
```
