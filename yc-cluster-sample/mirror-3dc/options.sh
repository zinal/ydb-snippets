# Настройки процесса установки YDB

# Имя промежуточного "хоста подскока", с которого видны создаваемые виртуалки
host_gw=gw1
# Базовое имя хоста, создаваемые виртуалки называются по шаблону ${host_base}-s{host_number}
host_base=ycydb
# Имя пользователя на виртуалках с правом на беспарольный sudo.
# Необходим беспарольный ssh-доступ с "хоста подскока".
host_user=yc-user

# Имя рабочего каталога для файлов установки YDB.
# Создаётся в домашнем каталоге на "хосте подскока" и виртуалках.
WORKDIR=YdbWork

# Имя файла публичного ключа на "хосте подскока",
# который нужно прописать при создании виртуалок для беспарольного входа.
keyfile_gw=.ssh/id_ecdsa.pub

# AZ Яндекс Облака, в которой создаются виртуалки
yc_zone=ru-central1-b
# Существующая подсеть в Яндекс Облаке
yc_subnet=default-ru-central1-b
# Тип платформы виртуалок, standard-v2 или standard-v3
yc_platform=standard-v2
# Выбранный образ операционной системы виртуалок
#yc_vm_image="image-folder-id=standard-images,image-family=ubuntu-2204-lts"
#yc_vm_image="image-folder-id=standard-images,image-name=astralinux-alse-v20230215"
#yc_vm_image="image-folder-id=standard-images,image-name=redsoft-red-os-standart-server-7-3-v20220810"
#yc_vm_image="image-folder-id=standard-images,image-name=almalinux-9-v20230417"
yc_vm_image="image-folder-id=standard-images,image-name=almalinux-v20230417"
# Количество vCPU каждой виртуалки
yc_vm_cores=8
# Объем оперативной памяти на одну виртуалку, Гбайт
yc_vm_mem=24
# Размер диска для данных YDB на одну виртуалку, Гбайт
yc_data_disk_size=186G
yc_data_disk_type=network-ssd-nonreplicated

# Количество узлов в кластере
ydb_nodes=9
# Количество дисков для данных YDB в каждом узле кластера
ydb_disk_count=1
# Имя файла конфигурации кластера из подкаталога conf
ydb_config=conf-9n-16c-tls.yaml
#ydb_config=conf-18n-32c-tls.yaml
# Использовать ли TLS-защиту трафика
ydb_tls=Y
# Количество создаваемых дисковых групп
ydb_disk_groups=3
# Количество добавляемых узлов в скриптах расширения кластера
ydb_nodes_extra=9

# Пароль для пользователя root в сервисе YDB.
# Используется (недоделанным пока) скриптом расширения конфигурации дисков.
#ydb_root_password=
ydb_root_password="passw0rd"

# Вид поставки дистрибутива - tar[.gz] или xz
# Должен лежать в каталоге ${WORKDIR} на "хосте подскока"
#YDBD_ARCHIVE=ydbd.xz
YDBD_ARCHIVE=ydbd.tar.gz

# End Of File