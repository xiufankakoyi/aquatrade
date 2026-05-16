<template>
  <div>
    <h3>调试信息</h3>
    <p>记录数: {{ records.length }}</p>
    <p>列数: {{ displayColumns.length }}</p>
    <p>列列表:</p>
    <ul>
      <li v-for="col in displayColumns" :key="col.key">{{ col.title }} ({{ col.dataIndex }})</li>
    </ul>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  records: Array
})

const defaultColumns = [
  { title: '股票代码', dataIndex: 'stock_code', key: 'stock_code' },
  { title: '收盘价', dataIndex: 'close', key: 'close' },
]

const extendedColumns = [
  { title: '相关系数(60)', dataIndex: 'corr_60d', key: 'corr_60d' },
]

const displayColumns = computed(() => {
  if (props.records.length === 0) return defaultColumns
  const recordKeys = Object.keys(props.records[0])
  const allColumns = [...defaultColumns, ...extendedColumns]
  return allColumns.filter(col => recordKeys.includes(col.dataIndex))
})
</script>
