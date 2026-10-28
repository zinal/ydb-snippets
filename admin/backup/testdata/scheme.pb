columns {
  name: "__Hash_id_gopa"
  type {
    optional_type {
      item {
        type_id: UINT64
      }
    }
  }
}
columns {
  name: "id_shard"
  type {
    optional_type {
      item {
        type_id: UTF8
      }
    }
  }
}
columns {
  name: "id_sort"
  type {
    optional_type {
      item {
        type_id: UTF8
      }
    }
  }
}
columns {
  name: "id_gopa"
  type {
    optional_type {
      item {
        type_id: UTF8
      }
    }
  }
}
columns {
  name: "id_zaspa"
  type {
    optional_type {
      item {
        type_id: UTF8
      }
    }
  }
}
columns {
  name: "__RowData"
  type {
    optional_type {
      item {
        type_id: JSON_DOCUMENT
      }
    }
  }
}
columns {
  name: "__Hash"
  type {
    optional_type {
      item {
        type_id: UINT64
      }
    }
  }
}
primary_key: "__Hash"
primary_key: "id_shard"
primary_key: "id_sort"
indexes {
  name: "ix1"
  index_columns: "__Hash_id_gopa"
  index_columns: "id_gopa"
  index_columns: "id_zaspa"
  index_columns: "id_shard"
  index_columns: "id_sort"
  global_async_index {
    settings {
      partitioning_settings {
        partitioning_by_size: ENABLED
        partition_size_mb: 2048
        partitioning_by_load: DISABLED
        min_partitions_count: 1
      }
    }
  }
  data_columns: "__RowData"
}
indexes {
  name: "ix2"
  index_columns: "__Hash_id_gopa"
  index_columns: "id_gopa"
  index_columns: "id_sort"
  index_columns: "id_shard"
  global_async_index {
    settings {
      partitioning_settings {
        partitioning_by_size: ENABLED
        partition_size_mb: 2048
        partitioning_by_load: DISABLED
        min_partitions_count: 1
      }
    }
  }
  data_columns: "id_zaspa"
  data_columns: "__RowData"
}
storage_settings {
  store_external_blobs: DISABLED
}
column_families {
  name: "default"
  compression: COMPRESSION_NONE
}
attributes {
  key: "__document_api_version"
  value: "20200804"
}
attributes {
  key: "dynamodbDataColumns"
  value: "{\"ix1\":[\"__RowData\"],\"ix2\":[\"id_zaspa\",\"__RowData\"]}"
}
attributes {
  key: "dynamodbIndexes"
  value: "{\"ix1\":\"AAIBBAQ=\",\"ix2\":\"AAIBBA==\"}"
}
partitioning_settings {
  partitioning_by_size: ENABLED
  partition_size_mb: 1024
  partitioning_by_load: ENABLED
  min_partitions_count: 1
}
