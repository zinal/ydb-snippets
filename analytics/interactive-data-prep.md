# Интерактивная подготовка данных в закрытом контуре

Короткий отчёт по двум вопросам: чем заменить сессию подготовки в духе Trifacta, если данные и управление должны остаться в своей сети, и насколько визуальный слой Data Refinery / Data Preparation полезен, когда трансформации пишет ИИ-агент.

Дата сверки: 17 ноября 2026.

## Вывод

Self-managed Trifacta (Alteryx Self-Managed Designer Cloud) снят с поддержки 31 декабря 2025. Предлагаемый вендором переход, Designer Cloud в Alteryx One, уводит контрольную плоскость в облако. В своей сети колоночный рецепт с прогоном на полном объёме закрывают Dataiku DSS, IBM Data Refinery и полностью локальный Talend Data Preparation 8. Если нужен реестр российского ПО, платформой остаётся Loginom. OpenRefine и Apache Hop закрывают отдельные куски сценария.

Визуальный слой при агентах полезен как контракт и проверка. Агент быстрее пишет однозначное преобразование. Сетка, профиль колонки и список шагов нужны, чтобы снять двусмысленность, увидеть хвост данных и поправить один шаг до полного прогона. Клики, которыми рецепт собирают с нуля, на коротких однозначных задачах качество не поднимают.

## Что ставить в закрытый контур

| Условие | Куда смотреть |
| --- | --- |
| Иностранная лицензия допустима, нужна колоночная сетка | Dataiku DSS: рецепт Prepare, движки DSS, SQL или Spark, файл лицензии |
| Та же сетка и документированный air-gap | IBM Data Refinery. Входной билет: OpenShift и Cloud Pak for Data |
| Реестр российского ПО | Loginom Server: сценарии, расписание, LDAP/OpenID, Linux или контейнер |
| Поток узлов, как в Alteryx Designer | KNIME Analytics Platform. Общий сервер — Business Hub с airgap-бандлом |
| Грязные категории на одной машине | OpenRefine |
| Промышленный поток без профайлера | Apache Hop |

Talend Data Preparation годится только в полной установке с Talend Administration Center. Hybrid оставляет данные у заказчика, а учётные записи и семантические типы синхронизирует с Talend Cloud. Self-Service ETL у Visiology, ETL Polymatica и Modus ETL готовят витрину для дашборда и не заменяют сессию исследования грязного файла.

Штатного исполнения визуального рецепта внутри YDB нет. Совместимый с PostgreSQL протокол покрывает не весь YQL. Рабочая схема: выборка уходит в инструмент, промышленный шаг пишется отдельно на YQL или пакетной загрузкой через SDK, планировщик только запускает этот шаг.

## Зачем сетка, если трансформацию пишет агент

На PrepBench лучшая из десяти моделей, GPT-5.1-Codex, собирает верную таблицу по исходному запросу в 54,9% задач. Когда двусмысленность из запроса уже убрана, точность поднимается до 85,3%. Интерактивное уточнение самих моделей слабое: F1 лучшей модели 51,4. Почти половина двусмысленностей в наборе — операционные: правило не покрывает край, два правила спорят за одну строку, порог не определён. Сквозной поток операторов верен в 34,6%. Перевод уже верного кода в такой поток удаётся в 67,7%. Агент должен сразу писать шаги каталога продукта. Просить модель нарисовать GUI из свободного Python вредно.

Человек судит карточки операторов точнее кода: 85,4% верных суждений против 72,9% при уверенности 4,1 против 3,6 из 5 (16 участников, PrepBench). В Dango (CHI 2025, 38 участников) чат сочли удобным способом выразить намерение 74–89%, демонстрацию на таблице — 21–29%. Доля сессий с галлюцинированным скриптом при этом упала с 0,65 до 0,18, когда к чату добавили редактируемые шаги и вопросы агента. Время сократилось на 32–45%. Выигрыш виден на условных и многотабличных задачах. На простых его нет.

Наблюдение 2026 года на 40 практиках (Excel, OpenRefine, Jupyter, ChatGPT) победителя по качеству чистки не нашло. Чат устойчивее на жёстко заданной чистке и слабее, когда надо самому решить, что считать грязью. В CITBench средняя результативность моделей падает примерно на 16% при усложнении правила, на 40% при нескольких входах и на 66% на многошаговых задачах относительно базового уровня.

Профиль колонки остаётся работой движка статистики. В 36,6% задач PrepBench грязь не видна в короткой выборке: разные форматы одного типа, разные обозначения пропуска, разные написания. Сравнение общих и табличных моделей («Lost in the Pipeline») показывает, что они приемлемо режут и склеивают колонки, находят точные дубликаты и пустые строки, плохо считают и почти не видят неточные дубликаты и пропуски вида `-1` или `--`.

## Как это уже устроено в продуктах

Быстрый старт Dataiku по подготовке данных фиксирует нужный разрыв выборки и полного прогона. В Explore видна выборка. Число строк и распределение колонки можно посчитать и по выборке, и по всему набору. Рецепт Prepare собирается из библиотеки процессоров, действий в заголовке колонки и формул. В учебном проекте колонку `location` режут по запятой не больше чем на три поля и переименовывают в `country`, `state`, `city`. Запуск рецепта применяет те же шаги ко всему входу и не меняет исходную таблицу. Join оставляет несошедшиеся строки отдельным набором, чтобы проверить допущение о ключе. Код из ноутбука вставляется в тот же визуальный поток. Движок рецепта (DSS, SQL, Spark) выбирается по месту хранения, данные не обязаны переезжать внутрь инструмента. В версии 15 Generate Steps по текстовому запросу кладёт шаги Prepare из этой же библиотеки. Человек проверяет шаги и превью, затем запускает рецепт.

IBM Data Refinery держит тот же разрыв: в интерфейсе выборка до 1 МБ или 10 000 строк, job исполняет поток на всём наборе. Пункт Natural Language в его меню — удаление стоп-слов и токенизация, а не агент. Ценность рядом с агентом — профиль и неизменный список шагов.

OpenRefine даёт прямое редактирование колонки, а не платформу с расписанием. Меню Edit column режет значение в несколько колонок по разделителю, длине или выражению, склеивает колонки в заданном порядке, строит новую колонку выражением GREL (`value`, `cells["Column"].value`) и умеет дописать колонку загрузкой URL с паузой между запросами (по умолчанию 5 секунд на строку) и записью ошибки. Переименование, перенос и удаление обратимы, пока история операций не ушла дальше. Это сильная точечная правка грязных категорий и слабый общий сервер.

Talend Magic Fill выводит строковый шаблон из двух–пяти примеров. На Spark и в выгрузку HDFS или S3 эта функция не переносится, промышленный шаг должен стать обычной функцией рецепта. Alteryx Copilot добавляет узлы на холст и сам фиксирует границу: данных он не видит, поток не запускает, конфигурацию нужно проверить перед запуском.

## Закрытый контур и слабая модель

На том же PrepBench лучшая открытая модель, Kimi K2 Thinking, даёт 49,7% сквозного кода и 30,1% сквозного потока против 54,9% и 34,6% у GPT-5.1-Codex. Слабые модели проваливаются сильнее: GPT-4o — 16,7% и 5,2%, DevStral 2 — 33,3% и 8,5%. В изолированной сети выбор модели важнее выбора между чатом и сеткой. Если доступна только младшая модель, безнадзорный прогон становится лотереей, и проверяемый рецепт остаётся основным способом удержать качество.

## Что требовать от инструмента

1. Агент пишет родные шаги продукта, а не параллельный скрипт.
2. Профиль колонки доступен агенту как инструмент движка.
3. Один шаг можно поправить без нового промпта.
4. Один и тот же рецепт исполняется на выборке и на полном объёме.
5. После полного прогона сверяются число строк, доля пустых, число различных значений и неожиданные типы.

Клики с нуля в этой схеме почти не участвуют. Их место — редкая правка и демонстрация на нескольких примерах, когда пример точнее фразы.

## Источники

Продукты и руководства:

- [OpenRefine. Column editing](https://openrefine.org/docs/manual/columnediting)
- [Dataiku 15. Quick Start: Dataiku for data preparation](https://knowledge.dataiku.com/latest/getting-started/tasks/data-prep/quick-start-index.html)
- [Dataiku 15. Generate Prepare recipe steps with AI](https://knowledge.dataiku.com/latest/prepare-transform-data/prepare/additional-data-prep/how-to-generate-steps.html)
- [Dataiku DSS 15. Cobuild](https://doc.dataiku.com/dss/latest/ai-assistants/cobuild.html)
- [Dataiku DSS 15. Agent Review](https://doc.dataiku.com/dss/latest/agents/agent-review.html)
- [IBM. Refining data with Data Refinery](https://dataplatform.cloud.ibm.com/docs/content/wsj/refinery/refining_data.html)
- [Alteryx. Product overview, снятие поддержки Self-Managed Designer Cloud](https://help.alteryx.com/smc/r104/en/product-overview.html)
- [Alteryx Copilot](https://help.alteryx.com/current/en/designer/alteryx-copilot.html)
- [KNIME Business Hub. Installation options](https://docs.knime.com/hub/latest/business_hub_installation_options_supported_environments/)
- [Talend 8. Product lifecycle](https://help.qlik.com/talend/en-US/customer-support-statements/cloud/product-end-of-life-planning)
- [Talend. Hybrid installation](https://help.qlik.com/talend/en-US/hybrid-installation-guide-linux/Cloud/what-is-hybrid-for-talend-cloud)
- [Talend. Automatically formatting data based on examples (Magic Fill)](https://help.qlik.com/talend/en-US/data-preparation-user-guide/Cloud/automatically-formatting-data-based-on-examples)
- [Loginom Server для Linux](https://help.loginom.ru/adminguide/linux/server/index.html)
- [Visiology. Self-Service ETL](https://ru.visiology.su/products/self-service-etl/)

Исследования:

- Wang et al. PrepBench: How Far Are We from Natural-Language-Driven Data Preparation? PVLDB, том 19. <https://www.vldb.org/pvldb/vol19/p2866-wang.pdf>
- Chen et al. Dango: A Mixed-Initiative Data Wrangling System using Large Language Model. CHI 2025. <https://dl.acm.org/doi/full/10.1145/3706598.3714135>
- He et al. How Wrangling Tools Shape Wrangling: A Technical Dimensions Analysis. <https://arxiv.org/html/2607.26198>
- CITBench: A Comprehensive Benchmark for Interactive Tabular Data Processing with LLMs. <https://arxiv.org/html/2608.00018v1>
- Lost in the Pipeline: How Well Do Large Language Models Handle Data Preparation? <https://arxiv.org/html/2511.21708v1>
