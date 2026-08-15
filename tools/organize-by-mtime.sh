#!/usr/bin/env bash
# Перемещает файлы из текущего каталога (без рекурсии) в ГГГГ/ММ/,
# исходя из даты последней модификации. Метка mtime сохраняется.
#
# Использование:
#   cd /path/with/files && /path/to/organize-by-mtime.sh
#
set -euo pipefail

shopt -s nullglob

moved=0
skipped=0

for path in ./* ./.[!.]* ./..?*; do
  # Только обычные файлы; каталоги, симлинки и спец. узлы пропускаем
  [[ -f "$path" && ! -L "$path" ]] || continue

  name=${path#./}

  # Не трогаем сам скрипт, если он лежит в этом каталоге
  if [[ "$(realpath "$path")" == "$(realpath "${BASH_SOURCE[0]}")" ]]; then
    continue
  fi

  # Эталон mtime до перемещения (включая доли секунды, если доступны)
  stamp=$(mktemp)
  touch -r "$path" "$stamp"

  year=$(date -r "$stamp" +%Y)
  month=$(date -r "$stamp" +%m)

  dest_dir="${year}/${month}"
  dest="${dest_dir}/${name}"

  if [[ -e "$dest" ]]; then
    echo "пропуск (уже существует): $name -> $dest" >&2
    rm -f "$stamp"
    skipped=$((skipped + 1))
    continue
  fi

  mkdir -p "$dest_dir"
  mv -- "$path" "$dest"
  # Явно восстанавливаем mtime на случай копирования между файловыми системами
  touch -r "$stamp" "$dest"
  rm -f "$stamp"

  echo "$name -> $dest"
  moved=$((moved + 1))
done

echo "готово: перемещено $moved, пропущено $skipped"
