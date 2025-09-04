Пример реализации интерактивной транзакции с использованием Query Service.

Задействован режим передачи параметров без явного определения их типа данных.
Для этого на стороне сервера YDB:

```yaml
table_service_config:
  enable_implicit_query_parameter_types: true
```

Для сборки и запуска требуется JDK 17+ и Maven.

Параметры подключения к БД прописываются в `example1.xml`.

При успешном выполнении рабочие таблички и схема удаляются.

```bash
mvn clean package
ydb scheme rmdir -r interactive-tx
mvn exec:java -Dexec.args=example1.xml
```
