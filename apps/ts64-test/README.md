Тест вставки и выборки значений Timestamp64 и Date32 с использованием Query Service.

Для сборки и запуска требуется JDK 8+ и Maven.

Параметры подключения к БД прописываются в `example1.xml`.

При успешном выполнении рабочие таблички и схема удаляются.

```bash
mvn clean package
ydb scheme rmdir -r ts64-test
mvn exec:java
```
