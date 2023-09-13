UTF-8

Набор инструментов для проведения тестов TPC-C над базами данных YDB.

Состав материалов:

1. OpenJDK20U-jdk_x64_linux_hotspot_20.0.2_9.tar.gz
   Сборка OpenJDK 20 (Eclipse Temurin), загружена с https://adoptium.net/temurin/releases/
   Исходные коды: https://github.com/openjdk/jdk/tree/jdk-20+9

2. custom-python.tgz
   Среда CPython 3.11, скомпилированная под AstraLinux.
   Исходный код: https://github.com/python/cpython/archive/refs/tags/v3.11.5.tar.gz
   Установленные пакеты Python:
     ydb
     pssh
     parallel-ssh
     virtualenv
     wheel
     numpy
     requests

3. benchbase-ydb.tgz
   Кастомизированная сборка Benchbase для YDB.
   Исходный код: https://github.com/ydb-platform/tpcc
   Исходный код драйвера JDBC для YDB (в составе): https://github.com/ydb-platform/ydb-jdbc-driver

4. tpcc-helpers-ydb.tgz
   Набор вспомогательных скриптов для автоматизации тестирования.

5. tpcc-steps.txt
   Инструкция-напоминание по настройке и выполнению теста TPC-C
