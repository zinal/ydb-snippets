-- Шаблон случайной выборки через TABLESAMPLE
-- (обычно дешевле, чем ORDER BY random() на больших таблицах).
--
-- SYSTEM — быстрее (по блокам), BERNOULLI — равномернее по строкам.
-- Подставьте имя таблицы и при необходимости долю/% LIMIT.

-- Пример просмотра:
--   SELECT * FROM public.big_table TABLESAMPLE SYSTEM (1) LIMIT 100;
--   SELECT * FROM public.big_table TABLESAMPLE BERNOULLI (0.5) LIMIT 100;

-- Пример выгрузки CSV из shell:
--   mkdir -p out/samples
--   psql -v ON_ERROR_STOP=1 -c \
--     "COPY (
--        SELECT * FROM public.users TABLESAMPLE SYSTEM (1) LIMIT 100
--      ) TO STDOUT WITH (FORMAT csv, HEADER true)" \
--     > out/samples/public_users.random.csv
