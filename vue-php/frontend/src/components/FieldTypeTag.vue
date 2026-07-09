<script setup lang="ts">
import { computed } from 'vue'
import { fieldTypeClass, fieldTypeLabel } from '@/utils/fieldTypes'

const props = defineProps<{ type: string }>()
const cls = computed(() => fieldTypeClass(props.type))
const label = computed(() => fieldTypeLabel(props.type))
</script>

<template>
  <span :class="cls">{{ label }}</span>
</template>
