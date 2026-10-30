<template>
  <section class="external-document-reader" aria-label="知识文档正文" :aria-busy="loading">
    <div class="reader-header">
      <strong>{{ title || '文档正文' }}</strong>
      <button type="button" class="reader-close" aria-label="关闭文档" @click="$emit('close')">
        关闭
      </button>
    </div>
    <p v-if="loading" role="status">正在读取文档…</p>
    <div v-else-if="error" role="alert">
      <p>{{ error }}</p>
      <a-button @click="load(initialOffset)">重新读取</a-button>
    </div>
    <template v-else-if="document">
      <p v-if="startLine" class="reader-position">按引用行号定位当前原文；文档更新后行号可能变化。</p>
      <p class="reader-position">
        第 {{ document.start_line }}–{{ document.end_line }} 行，共 {{ document.total_lines }} 行
      </p>
      <pre
        v-if="lines.length"
        class="reader-content"
        :style="{ '--line-number-width': `${String(document.end_line).length}ch` }"
      ><span v-for="line in lines" :key="line.number" class="reader-line" :class="{ 'reader-line-highlight': startLine && line.number >= startLine && line.number <= (endLine || startLine) }"><span class="reader-line-number" aria-hidden="true">{{ line.number }}</span><span class="reader-line-text">{{ line.text || '\u00a0' }}</span></span></pre>
      <p v-else class="reader-empty">文档正文为空</p>
      <nav
        v-if="document.has_more_before || document.has_more_after"
        class="reader-navigation"
        aria-label="文档分页"
      >
        <button
          type="button"
          class="reader-page-button"
          :disabled="!document.has_more_before"
          @click="load(Math.max(0, document.offset - document.window_size))"
        >
          <ChevronLeft :size="14" aria-hidden="true" />上一页
        </button>
        <button
          type="button"
          class="reader-page-button"
          :disabled="!document.has_more_after"
          @click="load(document.next_offset)"
        >
          下一页<ChevronRight :size="14" aria-hidden="true" />
        </button>
      </nav>
    </template>
  </section>
</template>

<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { ChevronLeft, ChevronRight } from '@lucide/vue'
import { queryApi } from '@/apis/knowledge_api'

const props = defineProps({
  kbId: { type: String, required: true },
  fileId: { type: String, required: true },
  title: { type: String, default: '' },
  startLine: { type: Number, default: null },
  endLine: { type: Number, default: null }
})
defineEmits(['close'])
const initialOffset = computed(() => Math.max(0, (props.startLine || 1) - 1))
const document = ref(null)
const loading = ref(false)
const error = ref('')
// 后端按“补齐的行号 + Tab + 正文”返回窗口，只拆开协议前缀，保留正文缩进。
const lines = computed(() =>
  document.value?.content
    ? document.value.content.split('\n').map((line, index) => ({
        number: document.value.start_line + index,
        text: line.slice(line.indexOf('\t') + 1)
      }))
    : []
)
let requestId = 0

/** 切换文档后丢弃旧请求，正文按页实时读取。 */
async function load(offset = 0) {
  const currentRequest = ++requestId
  loading.value = true
  error.value = ''
  document.value = null
  try {
    const result = await queryApi.openDocument(props.kbId, props.fileId, offset)
    if (currentRequest === requestId) document.value = result
  } catch (cause) {
    if (currentRequest === requestId) error.value = cause.message || '读取文档失败'
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}
watch(
  () => [props.kbId, props.fileId, props.startLine],
  () => load(initialOffset.value),
  { immediate: true }
)
onUnmounted(() => { requestId += 1 })
</script>

<style scoped lang="less">
.external-document-reader {
  padding: 16px;
  border: 1px solid var(--gray-200);
  border-radius: 8px;
  background: var(--gray-0);
  color: var(--color-text);
}
.reader-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.reader-close {
  border: 0;
  padding: 4px 8px;
  background: transparent;
  color: var(--color-text);
  cursor: pointer;
  font: inherit;
  &:focus-visible {
    outline: 2px solid var(--main-color);
    outline-offset: 2px;
  }
}
.reader-header strong {
  overflow-wrap: anywhere;
}
.reader-position {
  color: var(--color-text-secondary);
  font-size: 12px;
}
.reader-content {
  margin: 16px 0 0;
  padding: 0;
  background: transparent;
  font-size: 13px;
  line-height: 1.75;
}
.reader-line {
  display: grid;
  grid-template-columns: max(2ch, var(--line-number-width)) minmax(0, 1fr);
  gap: 12px;
}
.reader-line-highlight {
  background: var(--main-10);
}
.reader-line-number {
  color: var(--color-text-tertiary);
  text-align: right;
  user-select: none;
}
.reader-line-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.reader-empty {
  color: var(--color-text-secondary);
}
.reader-navigation {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--gray-150);
}
.reader-page-button {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 0;
  border-radius: 4px;
  padding: 4px 6px;
  background: transparent;
  color: var(--main-color);
  font: inherit;
  font-size: 12px;
  cursor: pointer;
  &:hover:not(:disabled) {
    background: var(--main-10);
  }
  &:disabled {
    color: var(--color-text-tertiary);
    cursor: default;
  }
  &:focus-visible {
    outline: 2px solid var(--main-color);
    outline-offset: 2px;
  }
}
</style>
