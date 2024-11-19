# YDB Insert5K

Пример реализации интерактивной транзакции, выполняющей параллельную (в X потоков) вставку N порций данных по Q записей в N разных таблиц с использованием Query Service.

Для сборки и запуска требуется JDK 17 и Maven.

Параметры подключения к БД прописываются в `example1.xml`.

При успешном выполнении рабочие таблички и схема удаляются.

```bash
mvn clean package
ydb scheme rmdir -r example-insert5k
mvn exec:java
mvn exec:java -Dexec.args=example2.xml
```

## Отладка

```
export MAVEN_OPTS='-Xdebug -Xrunjdwp:transport=dt_socket,server=y,address=8888,suspend=n'
mvn exec:java
```
