<script setup>
import { computed, reactive, ref, watch } from 'vue'

const STORAGE_KEY = 'paper-librarian-papers'

function loadPapers() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

const papers = ref(loadPapers())
const query = ref('')
const statusFilter = ref('all')
const collectionFilter = ref('all')
const citationStyle = ref('gb-t-7714')
const showForm = ref(false)
const showBasket = ref(false)
const editingId = ref(null)
const basket = ref([])
const isImporting = ref(false)
const fileInput = ref(null)
const manualPaperId = ref('')
const manualQuote = ref('')

const emptyForm = {
  title: '',
  authors: '',
  year: '',
  journal: '',
  volume: '',
  issue: '',
  pages: '',
  doi: '',
  tags: '',
  collection: '',
  status: 'unread',
  notes: ''
}

const form = reactive({ ...emptyForm })

const filteredPapers = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return papers.value.filter((paper) => {
    const matchStatus = statusFilter.value === 'all' || paper.status === statusFilter.value
    const matchCollection =
      collectionFilter.value === 'all' || paper.collection === collectionFilter.value
    const haystack = [
      paper.title,
      paper.authors,
      paper.year,
      paper.journal,
      paper.doi,
      paper.fullText || '',
      paper.collection || '',
      Array.isArray(paper.tags) ? paper.tags.join(' ') : ''
    ]
      .join(' ')
      .toLowerCase()
    const matchKeyword = !keyword || haystack.includes(keyword)
    return matchStatus && matchCollection && matchKeyword
  })
})

const collections = computed(() => {
  return [...new Set(papers.value.map((paper) => paper.collection).filter(Boolean))].sort()
})

const statusText = {
  unread: '未读',
  reading: '在读',
  read: '已读'
}

const basketPapers = computed(() => {
  return basket.value
    .map((id) => papers.value.find((paper) => paper.id === id))
    .filter(Boolean)
})

function save() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(papers.value))
}

function newId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function openAdd() {
  editingId.value = null
  Object.assign(form, emptyForm)
  showForm.value = true
}

function openEdit(paper) {
  editingId.value = paper.id
  Object.assign(form, {
    ...paper,
    tags: Array.isArray(paper.tags) ? paper.tags.join(', ') : paper.tags || '',
    collection: paper.collection || ''
  })
  showForm.value = true
}

function submitForm() {
  if (!form.title.trim()) {
    alert('请填写论文标题')
    return
  }

  if (editingId.value) {
    const index = papers.value.findIndex((paper) => paper.id === editingId.value)
    if (index !== -1) {
      papers.value[index] = {
        ...papers.value[index],
        ...form,
        tags: form.tags
          .split(/[,，、]/)
          .map((tag) => tag.trim())
          .filter(Boolean)
      }
    }
  } else {
    papers.value.unshift({
      id: newId(),
      ...form,
      tags: form.tags
        .split(/[,，、]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
      createdAt: new Date().toISOString()
    })
  }

  showForm.value = false
  save()
}

function deletePaper(id) {
  if (!confirm('确定删除这篇论文吗？')) return
  papers.value = papers.value.filter((paper) => paper.id !== id)
  basket.value = basket.value.filter((item) => item !== id)
  save()
}

function cycleStatus(paper) {
  const next = {
    unread: 'reading',
    reading: 'read',
    read: 'unread'
  }
  paper.status = next[paper.status]
  save()
}

function baseName(filePath) {
  return String(filePath).split(/[\\/]/).pop() || filePath
}

async function importFiles() {
  if (isImporting.value) return

  if (window.desktop?.selectFiles) {
    isImporting.value = true
    try {
      const files = await window.desktop.selectFiles()
      for (const file of files) {
        await addFileByPath(file)
      }
    } catch (error) {
      alert(`导入失败：${error.message || error}`)
    } finally {
      isImporting.value = false
    }
    return
  }

  fileInput.value?.click()
}

async function addFileByPath(filePath) {
  const fallback = {
    title: baseName(filePath).replace(/\.(pdf|docx)$/i, ''),
    authors: '',
    year: '',
    journal: '',
    volume: '',
    issue: '',
    pages: '',
    doi: '',
    confidence: 'none'
  }

  let metadata = fallback
  try {
    if (window.desktop?.extractMetadata) {
      metadata = await window.desktop.extractMetadata(filePath)
    }
  } catch {
    metadata = fallback
  }

  papers.value.unshift({
    id: newId(),
    title: metadata.title || fallback.title,
    authors: Array.isArray(metadata.authors)
      ? metadata.authors.join(', ')
      : metadata.authors || '',
    year: metadata.year || '',
    journal: metadata.journal || '',
    volume: metadata.volume || '',
    issue: metadata.issue || '',
    pages: metadata.pages || '',
    doi: metadata.doi || '',
    tags: [],
    collection: '',
    status: 'unread',
    notes: '',
    fileName: baseName(filePath),
    filePath,
    confidence: metadata.confidence || 'none',
    fullText: metadata.full_text || metadata.fullText || '',
    createdAt: new Date().toISOString()
  })

  save()
}

function onImport(event) {
  const files = Array.from(event.target.files || [])
  for (const file of files) {
    papers.value.unshift({
      id: newId(),
      title: file.name.replace(/\.pdf$/i, ''),
      authors: '',
      year: '',
      journal: '',
      volume: '',
      issue: '',
      pages: '',
      doi: '',
      tags: [],
      collection: '',
      status: 'unread',
      notes: '',
      fileName: file.name,
      confidence: 'none',
      createdAt: new Date().toISOString()
    })
  }
  event.target.value = ''
  save()
}

function toggleBasket(id) {
  const index = basket.value.indexOf(id)
  if (index === -1) {
    basket.value.push(id)
  } else {
    basket.value.splice(index, 1)
  }
}

function moveBasketItem(index, direction) {
  const target = index + direction
  if (target < 0 || target >= basket.value.length) return
  const item = basket.value.splice(index, 1)[0]
  basket.value.splice(target, 0, item)
}

function authorList(authors) {
  return authors
    .split(/[,，、;；]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function citationKey(paper, index = 0) {
  const firstAuthor = authorList(paper.authors)[0] || 'anonymous'
  const safeAuthor = firstAuthor.replace(/\s+/g, '').toLowerCase()
  return `${safeAuthor}${paper.year || 'noyear'}-${index + 1}`
}

function journalCitation(paper) {
  const authors = paper.authors || '佚名'
  const volume = paper.volume ? `, ${paper.volume}` : ''
  const issue = paper.issue ? `(${paper.issue})` : ''
  const pages = paper.pages ? `: ${paper.pages}` : ''
  return `${authors}. ${paper.title}[J]. ${paper.journal}, ${paper.year}${volume}${issue}${pages}.`
}

function apaCitation(paper) {
  const authors = paper.authors || 'Unknown'
  const year = paper.year || 'n.d.'
  const volume = paper.volume ? `, ${paper.volume}` : ''
  const issue = paper.issue ? `(${paper.issue})` : ''
  const pages = paper.pages ? `, ${paper.pages}` : ''
  return `${authors} (${year}). ${paper.title}. ${paper.journal}${volume}${issue}${pages}.`
}

function bibtexCitation(paper, index = 0) {
  return [
    `@article{${citationKey(paper, index)},`,
    `  author = {${paper.authors || 'Anonymous'}},`,
    `  title = {${paper.title}},`,
    `  journal = {${paper.journal || ''}},`,
    `  year = {${paper.year || ''}},`,
    `  volume = {${paper.volume || ''}},`,
    `  number = {${paper.issue || ''}},`,
    `  pages = {${paper.pages || ''}},`,
    `  doi = {${paper.doi || ''}}`,
    '}'
  ].join('\n')
}

function formatCitation(paper, index = 0) {
  if (citationStyle.value === 'apa') return apaCitation(paper)
  if (citationStyle.value === 'bibtex') return bibtexCitation(paper, index)
  return journalCitation(paper)
}

function copyText(text) {
  navigator.clipboard.writeText(text)
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

async function copyRichText(html, text) {
  if (navigator.clipboard && window.ClipboardItem) {
    try {
      await navigator.clipboard.write([
        new ClipboardItem({
          'text/html': new Blob([html], { type: 'text/html' }),
          'text/plain': new Blob([text], { type: 'text/plain' })
        })
      ])
      return
    } catch {
      // 回退到纯文本复制
    }
  }

  navigator.clipboard.writeText(text)
}

function copyBibliography() {
  if (!basketPapers.value.length) {
    alert('请先选择论文')
    return
  }
  const text = basketPapers.value
    .map((paper, index) => formatCitation(paper, index))
    .join('\n')
  copyText(text)
}

function bibliographyHtml() {
  const items = basketPapers.value
    .map((paper, index) => {
      return `<p style="margin-left:36pt; text-indent:-36pt;">${escapeHtml(
        formatCitation(paper, index)
      )}</p>`
    })
    .join('')
  return `<div>${items}</div>`
}

async function copyBibliographyAsWord() {
  if (!basketPapers.value.length) {
    alert('请先选择论文')
    return
  }

  const text = basketPapers.value
    .map((paper, index) => formatCitation(paper, index))
    .join('\n')
  await copyRichText(bibliographyHtml(), text)
}

function inTextCitation(paper, index) {
  if (citationStyle.value === 'apa') {
    const firstAuthor = authorList(paper.authors)[0] || 'Unknown'
    return `(${firstAuthor}, ${paper.year || 'n.d.'})`
  }

  if (citationStyle.value === 'bibtex') {
    return `\\cite{${citationKey(paper, index)}}`
  }

  return `[${index + 1}]`
}

function ensureInBasket(paper) {
  if (!basket.value.includes(paper.id)) {
    basket.value.push(paper.id)
  }
}

async function openOriginal(paper) {
  if (!paper.filePath) {
    alert('这篇论文没有记录本地文件路径')
    return
  }

  if (!window.desktop?.openPath) {
    alert('当前环境不支持打开本地文件')
    return
  }

  try {
    const errorMessage = await window.desktop.openPath(paper.filePath)
    if (errorMessage) {
      alert(`打开失败：${errorMessage}`)
    }
  } catch (error) {
    alert(`打开失败：${error.message || error}`)
  }
}

function copyManualQuote() {
  const quote = manualQuote.value.trim()
  if (!quote) {
    alert('请先粘贴要引用的原文段落')
    return
  }

  if (!manualPaperId.value) {
    alert('请选择这段原文对应的论文')
    return
  }

  const paper = papers.value.find((item) => item.id === manualPaperId.value)
  if (!paper) return

  ensureInBasket(paper)
  const index = basket.value.indexOf(paper.id)
  const marker = inTextCitation(paper, index)
  copyText(`“${quote}” ${marker}`)
}

async function copyManualQuoteAsWord() {
  const quote = manualQuote.value.trim()
  if (!quote) {
    alert('请先粘贴要引用的原文段落')
    return
  }

  if (!manualPaperId.value) {
    alert('请选择这段原文对应的论文')
    return
  }

  const paper = papers.value.find((item) => item.id === manualPaperId.value)
  if (!paper) return

  ensureInBasket(paper)
  const index = basket.value.indexOf(paper.id)
  const marker = inTextCitation(paper, index)
  const text = `“${quote}” ${marker}`
  const html = `<p style="margin-left:24pt;">“${escapeHtml(quote)}” ${escapeHtml(marker)}</p>`
  await copyRichText(html, text)
}

watch(papers, save, { deep: true })
</script>

<template>
  <main class="app-shell">
    <aside class="sidebar">
      <h1>论文库</h1>
      <nav>
        <button :class="{ active: statusFilter === 'all' }" @click="statusFilter = 'all'">
          全部论文
        </button>
        <button :class="{ active: statusFilter === 'unread' }" @click="statusFilter = 'unread'">
          未读
        </button>
        <button :class="{ active: statusFilter === 'reading' }" @click="statusFilter = 'reading'">
          在读
        </button>
        <button :class="{ active: statusFilter === 'read' }" @click="statusFilter = 'read'">
          已读
        </button>
      </nav>

      <div class="collection-section">
        <h2>我的集合</h2>
        <button :class="{ active: collectionFilter === 'all' }" @click="collectionFilter = 'all'">
          全部集合
        </button>
        <button
          v-for="collection in collections"
          :key="collection"
          :class="{ active: collectionFilter === collection }"
          @click="collectionFilter = collection"
        >
          {{ collection }}
        </button>
      </div>

      <div class="sidebar-footer">
        <button class="primary" @click="openAdd">添加论文</button>
        <button @click="showBasket = true">
          写作模式 <span v-if="basket.length">{{ basket.length }}</span>
        </button>
      </div>
    </aside>

    <section class="content">
      <header class="toolbar">
        <input v-model="query" type="search" placeholder="搜索标题、作者、年份、期刊" />
        <button class="primary" :disabled="isImporting" @click="importFiles">
          {{ isImporting ? '识别中…' : '导入 PDF / Word' }}
        </button>
        <input
          ref="fileInput"
          class="hidden-input"
          type="file"
          accept=".pdf,.docx"
          multiple
          @change="onImport"
        />
      </header>

      <div class="paper-list">
        <div v-if="!filteredPapers.length" class="empty-state">
          <p>没有匹配的论文</p>
          <button class="primary" @click="openAdd">添加第一篇论文</button>
        </div>

        <article v-for="paper in filteredPapers" :key="paper.id" class="paper-row">
          <div class="paper-main">
            <h2>{{ paper.title }}</h2>
            <p class="meta">
              {{ paper.authors || '作者未知' }}
              <span v-if="paper.year">· {{ paper.year }}</span>
              <span v-if="paper.journal">· {{ paper.journal }}</span>
              <span v-if="paper.collection">· 集合：{{ paper.collection }}</span>
              <span v-if="paper.tags && paper.tags.length">
                · 标签：{{ paper.tags.join('、') }}
              </span>
            </p>
            <p v-if="paper.notes" class="notes-preview">{{ paper.notes }}</p>
          </div>

          <div class="paper-actions">
            <button class="status" @click="cycleStatus(paper)">
              {{ statusText[paper.status] }}
            </button>
            <button @click="openOriginal(paper)">打开原文</button>
            <button @click="openEdit(paper)">编辑</button>
            <button @click="toggleBasket(paper.id)">
              {{ basket.includes(paper.id) ? '移出引用篮' : '加入引用篮' }}
            </button>
            <button @click="deletePaper(paper.id)">删除</button>
          </div>
        </article>
      </div>
    </section>

    <div v-if="showForm" class="modal-mask" @click.self="showForm = false">
      <div class="modal">
        <h2>{{ editingId ? '编辑论文' : '添加论文' }}</h2>

        <label>
          标题
          <input v-model="form.title" placeholder="论文标题" />
        </label>
        <label>
          作者
          <input v-model="form.authors" placeholder="多个作者用逗号分隔" />
        </label>
        <div class="form-grid">
          <label>
            年份
            <input v-model="form.year" placeholder="2024" />
          </label>
          <label>
            期刊
            <input v-model="form.journal" placeholder="期刊或会议名称" />
          </label>
          <label>
            卷
            <input v-model="form.volume" placeholder="卷号" />
          </label>
          <label>
            期
            <input v-model="form.issue" placeholder="期号" />
          </label>
          <label>
            页码
            <input v-model="form.pages" placeholder="1-10" />
          </label>
          <label>
            DOI
            <input v-model="form.doi" placeholder="10.xxxx/yyyy" />
          </label>
          <label>
            标签
            <input v-model="form.tags" placeholder="机器学习, 综述" />
          </label>
          <label>
            集合
            <input v-model="form.collection" placeholder="毕业论文" />
          </label>
        </div>
        <label>
          阅读状态
          <select v-model="form.status">
            <option value="unread">未读</option>
            <option value="reading">在读</option>
            <option value="read">已读</option>
          </select>
        </label>
        <label>
          笔记
          <textarea v-model="form.notes" rows="4" placeholder="记录你的想法"></textarea>
        </label>

        <div class="modal-actions">
          <button @click="showForm = false">取消</button>
          <button class="primary" @click="submitForm">保存</button>
        </div>
      </div>
    </div>

    <div v-if="showBasket" class="modal-mask" @click.self="showBasket = false">
      <div class="modal wide">
        <h2>写作模式</h2>

        <label>
          引用格式
          <select v-model="citationStyle">
            <option value="gb-t-7714">GB/T 7714-2015</option>
            <option value="apa">APA 7th</option>
            <option value="bibtex">BibTeX</option>
          </select>
        </label>

        <div class="manual-quote">
          <h3>手动粘贴引用</h3>
          <label>
            选择论文
            <select v-model="manualPaperId">
              <option value="">请选择论文</option>
              <option v-for="paper in papers" :key="paper.id" :value="paper.id">
                {{ paper.title }}
              </option>
            </select>
          </label>
          <label>
            粘贴原文段落
            <textarea v-model="manualQuote" rows="4" placeholder="用系统默认程序打开原文后，复制段落粘贴到这里"></textarea>
          </label>
          <button class="primary" @click="copyManualQuote">生成并复制引用</button>
          <button @click="copyManualQuoteAsWord">复制为 Word 格式</button>
        </div>

        <div v-if="!basketPapers.length" class="empty-state">
          <p>引用篮还是空的，先在论文列表中加入文献</p>
        </div>

        <div v-else class="basket-list">
          <div v-for="(paper, index) in basketPapers" :key="paper.id" class="basket-row">
            <span class="order">{{ index + 1 }}</span>
            <div>
              <p>{{ paper.title }}</p>
              <p>{{ formatCitation(paper, index) }}</p>
            </div>
            <div class="basket-actions">
              <button :disabled="index === 0" @click="moveBasketItem(index, -1)">上移</button>
              <button :disabled="index === basket.length - 1" @click="moveBasketItem(index, 1)">
                下移
              </button>
              <button @click="copyText(formatCitation(paper, index))">复制单条</button>
            </div>
          </div>
        </div>

        <div class="modal-actions">
          <button @click="showBasket = false">关闭</button>
          <button :disabled="!basketPapers.length" @click="copyBibliographyAsWord">
            复制为 Word 格式
          </button>
          <button class="primary" :disabled="!basketPapers.length" @click="copyBibliography">
            复制全部参考文献
          </button>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.app-shell {
  display: grid;
  grid-template-columns: 220px 1fr;
  height: 100vh;
}

.sidebar {
  background: #1f2937;
  color: #fff;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
}

.sidebar h1 {
  font-size: 20px;
  margin: 0 0 24px;
}

.sidebar nav {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sidebar button {
  background: transparent;
  border: none;
  color: #e5e7eb;
  text-align: left;
  padding: 10px 12px;
  border-radius: 8px;
}

.sidebar button:hover,
.sidebar button.active {
  background: #374151;
}

.collection-section {
  margin-top: 24px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.collection-section h2 {
  font-size: 12px;
  color: #9ca3af;
  margin: 0 0 4px;
  padding-left: 12px;
}

.sidebar-footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.content {
  padding: 24px;
  overflow: auto;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.toolbar input {
  flex: 1;
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

button,
.file-button {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: #e5e7eb;
  color: #1f2937;
  font-size: 14px;
}

button.primary {
  background: #2563eb;
  color: #fff;
}

.hidden-input {
  display: none;
}

.file-button {
  display: inline-flex;
  align-items: center;
  background: #2563eb;
  color: #fff;
  cursor: pointer;
}

.file-button input {
  display: none;
}

.paper-list {
  background: #fff;
  border-radius: 12px;
  overflow: hidden;
}

.paper-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px;
  border-bottom: 1px solid #e5e7eb;
}

.paper-main {
  min-width: 0;
}

.paper-main h2 {
  font-size: 16px;
  margin: 0 0 6px;
}

.meta,
.notes-preview {
  margin: 4px 0;
  color: #6b7280;
  font-size: 13px;
}

.paper-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.paper-actions .status {
  min-width: 52px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 120px 0;
  color: #6b7280;
}

.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
}

.modal {
  width: min(680px, 100%);
  max-height: 90vh;
  overflow: auto;
  background: #fff;
  border-radius: 12px;
  padding: 24px;
}

.modal.wide {
  width: min(820px, 100%);
}

.modal h2 {
  margin-top: 0;
}

.modal label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
  font-size: 14px;
}

.modal input,
.modal select,
.modal textarea {
  padding: 10px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font: inherit;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 16px;
}

.manual-quote {
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  margin: 16px 0;
  background: #f9fafb;
}

.manual-quote h3 {
  margin-top: 0;
}

.manual-quote button {
  margin-right: 8px;
}

.basket-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin: 16px 0;
}

.basket-row {
  display: grid;
  grid-template-columns: 28px 1fr auto;
  gap: 12px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
}

.order {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #2563eb;
  color: #fff;
}

.basket-row p {
  margin: 0 0 4px;
}

.basket-actions {
  display: flex;
  align-items: center;
  gap: 6px;
}

.basket-actions button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
