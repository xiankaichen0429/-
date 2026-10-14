<template>
  <main class="app-shell">
    <aside class="sidebar">
      <h1>论文库</h1>
      <nav>
        <button>全部论文</button>
        <button>待整理</button>
        <button>未读</button>
        <button>在读</button>
        <button>已读</button>
        <button>笔记</button>
      </nav>
    </aside>

    <section class="content">
      <header class="toolbar">
        <input type="search" placeholder="搜索标题、作者、年份" />
        <button>导入 PDF</button>
        <button>写作模式</button>
      </header>

      <div class="paper-list">
        <div class="empty-state">
          <p>还没有导入论文</p>
          <button>导入第一篇论文</button>
        </div>
      </div>
    </section>
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

.sidebar button:hover {
  background: #374151;
}

.content {
  padding: 24px;
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

.toolbar button,
.empty-state button {
  padding: 10px 16px;
  border: none;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
}

.paper-list {
  min-height: 480px;
  background: #fff;
  border-radius: 12px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  padding: 120px 0;
  color: #6b7280;
}
</style>
