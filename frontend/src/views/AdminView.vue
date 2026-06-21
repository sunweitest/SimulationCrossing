<template>
  <div class="admin-page">
    <!-- 密钥门控 -->
    <div v-if="!authenticated" class="gate-overlay">
      <div class="gate-card">
        <h1>🔧 管理后台</h1>
        <p class="gate-desc">请输入管理密钥以访问后台功能</p>
        <div class="gate-row">
          <input
            v-model="adminKey"
            type="password"
            class="input"
            placeholder="管理密钥"
            @keyup.enter="authenticate"
          />
          <button class="btn btn-primary" @click="authenticate" :disabled="authenticating">
            {{ authenticating ? '验证中...' : '进入' }}
          </button>
        </div>
        <div v-if="gateError" class="error-message">{{ gateError }}</div>
      </div>
    </div>

    <!-- 管理内容 -->
    <template v-if="authenticated">
      <!-- 顶部栏 -->
      <div class="top-bar">
        <h1>🔧 管理后台</h1>
        <div class="tab-nav">
          <button :class="['tab-btn', { active: activeTab === 'users' }]" @click="activeTab = 'users'">用户管理</button>
          <button :class="['tab-btn', { active: activeTab === 'novels' }]" @click="activeTab = 'novels'">小说/时间线</button>
          <button :class="['tab-btn', { active: activeTab === 'characters' }]" @click="activeTab = 'characters'">角色管理</button>
        </div>
        <router-link to="/character-create" class="back-link">← 返回</router-link>
      </div>

      <!-- 消息提示 -->
      <div v-if="message" :class="messageType === 'error' ? 'toast toast-error' : 'toast toast-success'">{{ message }}</div>

      <!-- Tab 1: 用户管理 -->
      <div v-if="activeTab === 'users'" class="tab-content">
        <div class="card">
          <h3>查找用户</h3>
          <div class="lookup-row">
            <input v-model="searchQuery" type="text" class="input" placeholder="输入邮箱或手机号" @keyup.enter="lookupUser" />
            <button class="btn btn-primary" @click="lookupUser" :disabled="lookingUp">
              {{ lookingUp ? '查找中...' : '查找' }}
            </button>
          </div>
        </div>

        <div v-if="user" class="card">
          <h3>用户信息</h3>
          <div class="user-detail">
            <div class="stat-item"><span class="stat-label">ID</span><span class="stat-value">{{ user.id }}</span></div>
            <div class="stat-item"><span class="stat-label">邮箱</span><span class="stat-value">{{ user.email || '—' }}</span></div>
            <div class="stat-item"><span class="stat-label">手机号</span><span class="stat-value">{{ user.phone || '—' }}</span></div>
            <div class="stat-item"><span class="stat-label">注册时间</span><span class="stat-value">{{ formatDate(user.created_at) }}</span></div>
            <div class="stat-item">
              <span class="stat-label">额外配额</span>
              <span class="stat-value"><span :class="user.extra_quota > 0 ? 'badge badge-success' : 'badge'">{{ user.extra_quota }} 次</span></span>
            </div>
            <div class="stat-item">
              <span class="stat-label">30天不限次数</span>
              <span class="stat-value">
                <span v-if="user.is_unlimited" class="badge badge-success">已开通（剩 {{ user.unlimited_days_left }} 天）</span>
                <span v-else class="text-muted">未开通</span>
              </span>
            </div>
          </div>
          <div class="actions">
            <div class="action-card">
              <h4>追加次数</h4>
              <div class="action-row">
                <input v-model.number="quotaAmount" type="number" class="input" placeholder="输入次数" min="1" style="max-width:200px" />
                <button class="btn btn-primary" @click="addQuota" :disabled="!quotaAmount || addingQuota">{{ addingQuota ? '处理中...' : '追加' }}</button>
              </div>
            </div>
            <div class="action-card">
              <h4>30天不限次数</h4>
              <div class="action-row">
                <button v-if="!user.is_unlimited" class="btn btn-delete-danger" @click="setUnlimited" :disabled="settingUnlimited">{{ settingUnlimited ? '处理中...' : '开通' }}</button>
                <button v-else class="btn btn-secondary" @click="cancelUnlimited" :disabled="cancelingUnlimited">{{ cancelingUnlimited ? '处理中...' : '取消' }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab 2: 小说/时间线管理 -->
      <div v-if="activeTab === 'novels'" class="tab-content">
        <div class="novel-layout">
          <div class="novel-list">
            <div class="section-header">
              <h3>小说列表</h3>
              <button class="btn btn-sm btn-primary" @click="openNovelForm()">+ 新建</button>
            </div>
            <div v-if="novelsLoading" class="text-muted">加载中...</div>
            <div v-for="(n, i) in novels" :key="n.id" :class="['novel-item', { active: selectedNovel?.id === n.id }]" @click="selectNovel(n)">
              <span class="novel-sort">{{ n.sort_order }}</span>
              <span class="novel-name">{{ n.name }}</span>
              <span class="novel-meta">{{ n.timeline_count }} 时间线</span>
              <div class="novel-actions">
                <button class="btn-icon" @click.stop="moveNovel(i, -1)" :disabled="i===0" title="上移">▲</button>
                <button class="btn-icon" @click.stop="moveNovel(i, 1)" :disabled="i===novels.length-1" title="下移">▼</button>
                <button class="btn-icon" @click.stop="openNovelForm(n)" title="编辑">✏️</button>
                <button class="btn-icon" @click.stop="deleteNovelConfirm(n)" title="删除">🗑️</button>
              </div>
            </div>
          </div>

          <div class="timeline-panel">
            <div v-if="selectedNovel" class="section-header">
              <h3>{{ selectedNovel.name }} — 时间节点</h3>
              <button class="btn btn-sm btn-primary" @click="openTimelineForm()">+ 新建</button>
            </div>
            <div v-if="!selectedNovel" class="text-muted" style="padding:2rem;text-align:center">← 选择左侧小说查看时间节点</div>
            <div v-if="selectedNovel && timelinesLoading" class="text-muted">加载中...</div>
            <div v-for="t in timelines" :key="t.id" class="timeline-item">
              <div class="tl-info">
                <strong>{{ t.name }}</strong>
                <span class="tl-desc">{{ t.description || '—' }}</span>
                <span class="tl-sort">排序: {{ t.sort_order }}</span>
              </div>
              <div class="tl-actions">
                <button class="btn-icon" @click="openTimelineForm(t)" title="编辑">✏️</button>
                <button class="btn-icon" @click="deleteTimelineConfirm(t)" title="删除">🗑️</button>
              </div>
            </div>
          </div>
        </div>

        <!-- 小说编辑弹窗 -->
        <div v-if="novelForm" class="modal-mask" @click.self="novelForm = null">
          <div class="modal-card">
            <h3>{{ editingNovel ? '编辑小说' : '新建小说' }}</h3>
            <div class="input-group"><label>名称</label><input v-model="novelForm.name" class="input" /></div>
            <div class="input-group"><label>描述</label><input v-model="novelForm.description" class="input" /></div>
            <div class="input-group"><label>排序</label><input v-model.number="novelForm.sort_order" type="number" class="input" style="max-width:120px" /></div>
            <div v-if="novelFormError" class="error-message">{{ novelFormError }}</div>
            <div class="modal-actions">
              <button class="btn" @click="novelForm = null">取消</button>
              <button class="btn btn-primary" @click="saveNovel" :disabled="novelSaving">{{ novelSaving ? '保存中...' : '保存' }}</button>
            </div>
          </div>
        </div>

        <!-- 时间线编辑弹窗 -->
        <div v-if="timelineForm" class="modal-mask" @click.self="timelineForm = null">
          <div class="modal-card">
            <h3>{{ editingTimeline ? '编辑时间节点' : '新建时间节点' }}</h3>
            <div class="input-group"><label>名称</label><input v-model="timelineForm.name" class="input" /></div>
            <div class="input-group"><label>描述</label><input v-model="timelineForm.description" class="input" /></div>
            <div class="input-group"><label>排序</label><input v-model.number="timelineForm.sort_order" type="number" class="input" style="max-width:120px" /></div>
            <div v-if="timelineFormError" class="error-message">{{ timelineFormError }}</div>
            <div class="modal-actions">
              <button class="btn" @click="timelineForm = null">取消</button>
              <button class="btn btn-primary" @click="saveTimeline" :disabled="timelineSaving">{{ timelineSaving ? '保存中...' : '保存' }}</button>
            </div>
          </div>
        </div>

        <!-- 删除确认 -->
        <div v-if="deleteTarget" class="modal-mask" @click.self="deleteTarget = null">
          <div class="modal-card modal-sm">
            <h3>确认删除</h3>
            <p>确定要删除「{{ deleteTarget.name }}」吗？此操作不可撤销。</p>
            <div v-if="deleteError" class="error-message">{{ deleteError }}</div>
            <div class="modal-actions">
              <button class="btn" @click="deleteTarget = null">取消</button>
              <button class="btn btn-delete-danger" @click="execDelete" :disabled="deleting">{{ deleting ? '删除中...' : '确认删除' }}</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Tab 3: 角色管理 -->
      <div v-if="activeTab === 'characters'" class="tab-content">
        <div class="char-toolbar">
          <select v-model="charFilterNovel" class="input" style="max-width:180px" @change="loadAdminCharacters">
            <option value="">全部小说</option>
            <option v-for="n in novels" :key="n.id" :value="n.name">{{ n.name }}</option>
          </select>
          <input v-model="charFilterSearch" class="input" placeholder="搜索角色名..." style="max-width:200px" @keyup.enter="loadAdminCharacters" />
          <button class="btn btn-primary" @click="loadAdminCharacters">筛选</button>
          <div style="margin-left:auto;display:flex;gap:8px;">
            <button class="btn" @click="downloadTemplate">📥 模板</button>
            <label class="btn btn-primary" style="cursor:pointer">
              📤 批量导入
              <input type="file" accept=".xlsx,.xls" @change="handleFileUpload" style="display:none" />
            </label>
          </div>
          <button class="btn btn-primary" @click="openCharForm()">+ 新建角色</button>
        </div>

        <div v-if="importResult" :class="importResult.errors?.length ? 'toast toast-error' : 'toast toast-success'" style="position:static;margin-bottom:16px;transform:none;">
          {{ importResult.message }}
          <span v-if="importResult.errors?.length">（{{ importResult.errors.length }} 个错误）</span>
        </div>

        <div v-if="adminCharactersLoading" class="text-muted" style="padding:2rem;text-align:center">加载中...</div>

        <div v-for="c in adminCharacters" :key="c.id" class="char-card">
          <div class="char-main">
            <div class="char-info">
              <strong>{{ c.name }}</strong>
              <span>{{ c.gender }} · {{ c.age }}岁 · {{ c.rank }}</span>
              <span class="char-novel">{{ c.novel }} · {{ c.timelines.length }} 时间节点 · {{ c.starting_points }} 积分</span>
            </div>
            <div class="char-actions">
              <button class="btn btn-sm" @click="openCharForm(c)">✏️ 编辑</button>
              <button class="btn btn-sm btn-delete-danger" @click="deleteCharConfirm(c)">🗑️ 删除</button>
            </div>
          </div>
          <div v-if="c.background" class="char-bg">{{ c.background }}</div>
          <div v-if="c.timelines.length" class="char-timelines">
            <span class="tl-tag" v-for="t in c.timelines" :key="t.timeline">{{ t.timeline }}</span>
          </div>
        </div>

        <!-- 角色编辑弹窗 -->
        <div v-if="charForm" class="modal-mask" @click.self="charForm = null">
          <div class="modal-card modal-lg">
            <h3>{{ editingChar ? '编辑角色' : '新建角色' }}</h3>
            <div class="char-form-grid">
              <div class="input-group"><label>小说</label><input v-model="charForm.novel" class="input" /></div>
              <div class="input-group"><label>姓名</label><input v-model="charForm.name" class="input" /></div>
              <div class="input-group"><label>性别</label>
                <select v-model="charForm.gender" class="input"><option>男性</option><option>女性</option></select>
              </div>
              <div class="input-group"><label>年龄</label><input v-model.number="charForm.age" type="number" class="input" /></div>
              <div class="input-group"><label>身份</label><input v-model="charForm.rank" class="input" /></div>
              <div class="input-group"><label>初始积分</label><input v-model.number="charForm.starting_points" type="number" class="input" /></div>
            </div>
            <div class="input-group"><label>角色背景</label><textarea v-model="charForm.background" class="input" rows="3"></textarea></div>

            <div class="char-timelines-editor">
              <div class="section-header"><h4>时间节点配置</h4><button class="btn btn-sm btn-primary" @click="addTimelineEntry">+ 添加</button></div>
              <div v-for="(tl, i) in charForm.timelines" :key="i" class="tl-entry">
                <div class="tl-entry-row">
                  <input v-model="tl.timeline" class="input" placeholder="时间节点名" style="flex:1" />
                  <button class="btn btn-sm btn-delete-danger" @click="charForm.timelines.splice(i,1)">✕</button>
                </div>
                <input v-model="tl.background" class="input" placeholder="时间节点背景（可选）" />
                <textarea v-model="tl.initial_scene" class="input" rows="2" placeholder="初始场景描述"></textarea>
              </div>
            </div>

            <div v-if="charFormError" class="error-message">{{ charFormError }}</div>
            <div class="modal-actions">
              <button class="btn" @click="charForm = null">取消</button>
              <button class="btn btn-primary" @click="saveChar" :disabled="charSaving">{{ charSaving ? '保存中...' : '保存' }}</button>
            </div>
          </div>
        </div>

        <!-- 删除确认 -->
        <div v-if="charDeleteTarget" class="modal-mask" @click.self="charDeleteTarget = null">
          <div class="modal-card modal-sm">
            <h3>确认删除</h3>
            <p>确定要删除角色「{{ charDeleteTarget.name }}」吗？</p>
            <div v-if="deleteError" class="error-message">{{ deleteError }}</div>
            <div class="modal-actions">
              <button class="btn" @click="charDeleteTarget = null">取消</button>
              <button class="btn btn-delete-danger" @click="execCharDelete" :disabled="deleting">{{ deleting ? '删除中...' : '确认删除' }}</button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, watch } from 'vue'
import { adminAPI } from '@/api'

// ====== 密钥门控 ======
const authenticated = ref(false)
const authenticating = ref(false)
const gateError = ref('')
const adminKey = ref('')

const authenticate = async () => {
  if (!adminKey.value) { gateError.value = '请输入管理密钥'; return }
  authenticating.value = true
  gateError.value = ''
  try {
    await adminAPI.listNovels(adminKey.value)
    authenticated.value = true
  } catch (err) {
    gateError.value = err.response?.data?.detail || err.response?.status === 403 ? '密钥无效' : '验证失败，请检查网络'
  } finally {
    authenticating.value = false
  }
}

// ====== Tab ======
const activeTab = ref('users')

// ====== 消息 ======
const message = ref('')
const messageType = ref('success')
const showMessage = (msg, type = 'success') => {
  message.value = msg; messageType.value = type
  setTimeout(() => { message.value = '' }, 4000)
}

// ====== 用户管理 ======
const searchQuery = ref('')
const lookingUp = ref(false)
const user = ref(null)
const quotaAmount = ref(null)
const addingQuota = ref(false)
const settingUnlimited = ref(false)
const cancelingUnlimited = ref(false)

const formatDate = (d) => d ? new Date(d).toLocaleString('zh-CN') : ''

const lookupUser = async () => {
  if (!searchQuery.value.trim()) { showMessage('请输入邮箱或手机号', 'error'); return }
  lookingUp.value = true; user.value = null
  try {
    user.value = await adminAPI.lookupUser(searchQuery.value.trim(), adminKey.value)
  } catch (err) {
    showMessage(err.response?.data?.detail || '查找失败', 'error')
  } finally { lookingUp.value = false }
}

const addQuota = async () => {
  if (!quotaAmount.value || quotaAmount.value < 1) return
  addingQuota.value = true
  try {
    const r = await adminAPI.addQuota(user.value.id, quotaAmount.value, adminKey.value)
    showMessage(r.message || '追加成功'); quotaAmount.value = null; await lookupUser()
  } catch (err) { showMessage(err.response?.data?.detail || '操作失败', 'error') }
  finally { addingQuota.value = false }
}

const setUnlimited = async () => {
  settingUnlimited.value = true
  try { await adminAPI.setUnlimited(user.value.id, adminKey.value); showMessage('已开通'); await lookupUser() }
  catch (err) { showMessage(err.response?.data?.detail || '操作失败', 'error') }
  finally { settingUnlimited.value = false }
}

const cancelUnlimited = async () => {
  cancelingUnlimited.value = true
  try { await adminAPI.cancelUnlimited(user.value.id, adminKey.value); showMessage('已取消'); await lookupUser() }
  catch (err) { showMessage(err.response?.data?.detail || '操作失败', 'error') }
  finally { cancelingUnlimited.value = false }
}

// ====== 小说/时间线管理 ======
const novels = ref([])
const novelsLoading = ref(false)
const selectedNovel = ref(null)
const timelines = ref([])
const timelinesLoading = ref(false)

const loadNovels = async () => {
  novelsLoading.value = true
  try { novels.value = await adminAPI.listNovels(adminKey.value) }
  catch (err) { showMessage(err.response?.data?.detail || '加载小说失败', 'error') }
  finally { novelsLoading.value = false }
}

const moveNovel = async (index, direction) => {
  const a = novels.value[index]
  const b = novels.value[index + direction]
  if (!a || !b) return
  const tmp = a.sort_order
  // 交换排序值
  await adminAPI.updateNovel(a.id, { sort_order: b.sort_order }, adminKey.value)
  await adminAPI.updateNovel(b.id, { sort_order: tmp }, adminKey.value)
  await loadNovels()
}

const selectNovel = async (n) => {
  selectedNovel.value = n
  timelinesLoading.value = true
  try { timelines.value = await adminAPI.listTimelines(n.id, adminKey.value) }
  catch (err) { showMessage(err.response?.data?.detail || '加载时间节点失败', 'error') }
  finally { timelinesLoading.value = false }
}

// 小说表单
const novelForm = ref(null)
const editingNovel = ref(null)
const novelSaving = ref(false)
const novelFormError = ref('')

const openNovelForm = (n) => {
  editingNovel.value = n || null
  novelForm.value = n
    ? { name: n.name, description: n.description || '', sort_order: n.sort_order }
    : { name: '', description: '', sort_order: 0 }
  novelFormError.value = ''
}

const saveNovel = async () => {
  if (!novelForm.value.name.trim()) { novelFormError.value = '请输入名称'; return }
  novelSaving.value = true; novelFormError.value = ''
  try {
    if (editingNovel.value) {
      await adminAPI.updateNovel(editingNovel.value.id, novelForm.value, adminKey.value)
    } else {
      await adminAPI.createNovel(novelForm.value, adminKey.value)
    }
    novelForm.value = null; editingNovel.value = null
    await loadNovels(); showMessage('保存成功')
  } catch (err) { novelFormError.value = err.response?.data?.detail || '保存失败' }
  finally { novelSaving.value = false }
}

// 时间线表单
const timelineForm = ref(null)
const editingTimeline = ref(null)
const timelineSaving = ref(false)
const timelineFormError = ref('')

const openTimelineForm = (t) => {
  editingTimeline.value = t || null
  timelineForm.value = t
    ? { name: t.name, description: t.description || '', sort_order: t.sort_order }
    : { name: '', description: '', sort_order: 0 }
  timelineFormError.value = ''
}

const saveTimeline = async () => {
  if (!timelineForm.value.name.trim()) { timelineFormError.value = '请输入名称'; return }
  timelineSaving.value = true; timelineFormError.value = ''
  try {
    if (editingTimeline.value) {
      await adminAPI.updateTimeline(editingTimeline.value.id, timelineForm.value, adminKey.value)
    } else {
      await adminAPI.createTimeline({ ...timelineForm.value, novel_id: selectedNovel.value.id }, adminKey.value)
    }
    timelineForm.value = null; editingTimeline.value = null
    await selectNovel(selectedNovel.value); showMessage('保存成功')
  } catch (err) { timelineFormError.value = err.response?.data?.detail || '保存失败' }
  finally { timelineSaving.value = false }
}

// 删除
const deleteTarget = ref(null)
const deleting = ref(false)
const deleteError = ref('')

const deleteNovelConfirm = (n) => { deleteTarget.value = { ...n, _type: 'novel' }; deleteError.value = '' }
const deleteTimelineConfirm = (t) => { deleteTarget.value = { ...t, _type: 'timeline' }; deleteError.value = '' }

const execDelete = async () => {
  deleting.value = true; deleteError.value = ''
  try {
    if (deleteTarget.value._type === 'novel') {
      await adminAPI.deleteNovel(deleteTarget.value.id, adminKey.value)
      selectedNovel.value = null; timelines.value = []
      await loadNovels()
    } else {
      await adminAPI.deleteTimeline(deleteTarget.value.id, adminKey.value)
      await selectNovel(selectedNovel.value)
    }
    deleteTarget.value = null; showMessage('已删除')
  } catch (err) { deleteError.value = err.response?.data?.detail || '删除失败' }
  finally { deleting.value = false }
}

// ====== 角色管理 ======
const adminCharacters = ref([])
const adminCharactersLoading = ref(false)
const charFilterNovel = ref('')
const charFilterSearch = ref('')
const charForm = ref(null)
const editingChar = ref(null)
const charSaving = ref(false)
const charFormError = ref('')
const charDeleteTarget = ref(null)

const loadAdminCharacters = async () => {
  adminCharactersLoading.value = true
  try {
    const params = {}
    if (charFilterNovel.value) params.novel = charFilterNovel.value
    if (charFilterSearch.value) params.search = charFilterSearch.value
    adminCharacters.value = await adminAPI.listCharacters(params, adminKey.value)
  } catch (err) { showMessage(err.response?.data?.detail || '加载角色失败', 'error') }
  finally { adminCharactersLoading.value = false }
}

const openCharForm = (c) => {
  editingChar.value = c || null
  charForm.value = c
    ? {
        novel: c.novel, name: c.name, gender: c.gender, age: c.age,
        rank: c.rank, background: c.background || '', starting_points: c.starting_points,
        timelines: c.timelines.map(t => ({ ...t })),
      }
    : {
        novel: '', name: '', gender: '男性', age: 25, rank: '未知',
        background: '', starting_points: 0, timelines: [],
      }
  charFormError.value = ''
}

const addTimelineEntry = () => {
  charForm.value.timelines.push({ timeline: '', background: '', initial_scene: '' })
}

const saveChar = async () => {
  if (!charForm.value.name.trim()) { charFormError.value = '请输入角色姓名'; return }
  if (!charForm.value.novel.trim()) { charFormError.value = '请输入小说名称'; return }
  charSaving.value = true; charFormError.value = ''
  try {
    if (editingChar.value) {
      await adminAPI.updateCharacter(editingChar.value.id, charForm.value, adminKey.value)
    } else {
      await adminAPI.createCharacter(charForm.value, adminKey.value)
    }
    charForm.value = null; editingChar.value = null
    await loadAdminCharacters(); showMessage('保存成功')
  } catch (err) { charFormError.value = err.response?.data?.detail || '保存失败' }
  finally { charSaving.value = false }
}

const deleteCharConfirm = (c) => { charDeleteTarget.value = c; deleteError.value = '' }

const execCharDelete = async () => {
  deleting.value = true; deleteError.value = ''
  try {
    await adminAPI.deleteCharacter(charDeleteTarget.value.id, adminKey.value)
    charDeleteTarget.value = null; await loadAdminCharacters(); showMessage('已删除')
  } catch (err) { deleteError.value = err.response?.data?.detail || '删除失败' }
  finally { deleting.value = false }
}

// ====== 批量导入 ======
const importResult = ref(null)

const downloadTemplate = () => {
  const a = document.createElement('a')
  a.href = `/api/admin/characters/template`
  // Pass admin key via query param for simplicity
  a.href += `?token=${encodeURIComponent(adminKey.value)}`
  // Actually, we need to use the header. Let's use a fetch-based download instead.
  // Since it's a GET with header, we use fetch + blob
  fetch('/api/admin/character-template', {
    headers: { 'X-Admin-Key': adminKey.value }
  })
    .then(r => {
      if (!r.ok) throw new Error('下载失败')
      return r.blob()
    })
    .then(blob => {
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'character_import_template.xlsx'
      a.click()
      URL.revokeObjectURL(url)
    })
    .catch(err => showMessage(err.message || '模板下载失败', 'error'))
}

const handleFileUpload = async (e) => {
  const file = e.target.files?.[0]
  if (!file) return
  importResult.value = null
  try {
    const formData = new FormData()
    formData.append('file', file)
    const resp = await fetch('/api/admin/character-import', {
      method: 'POST',
      headers: { 'X-Admin-Key': adminKey.value },
      body: formData,
    })
    const data = await resp.json()
    if (!resp.ok) throw new Error(data.detail || '导入失败')
    importResult.value = data
    showMessage(data.message)
    await loadAdminCharacters()
  } catch (err) {
    showMessage(err.message || '导入失败', 'error')
  }
  e.target.value = ''  // reset file input
}

// ====== 初始化 ======
watch(authenticated, (val) => {
  if (val) { loadNovels(); loadAdminCharacters() }
})
</script>

<style scoped>
.admin-page {
  min-height: 100vh;
  background: #0d1117;
  color: #c9d1d9;
}

/* ===== 密钥门控 ===== */
.gate-overlay {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 2rem;
}

.gate-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 3rem;
  max-width: 440px;
  width: 100%;
  text-align: center;
}

.gate-card h1 { font-size: 1.6rem; margin-bottom: 0.5rem; }
.gate-desc { color: #8b949e; margin-bottom: 1.5rem; }

.gate-row {
  display: flex;
  gap: 0.75rem;
}

.gate-row .input {
  flex: 1;
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #30363d;
  background: #0d1117;
  color: #c9d1d9;
  font-size: 0.95rem;
}

/* ===== 顶部栏 ===== */
.top-bar {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  padding: 16px 28px;
  background: #161b22;
  border-bottom: 1px solid #30363d;
  position: sticky;
  top: 0;
  z-index: 100;
}

.top-bar h1 { font-size: 1.2rem; margin: 0; white-space: nowrap; }

.tab-nav { display: flex; gap: 4px; }

.tab-btn {
  padding: 7px 18px;
  border: 1px solid transparent;
  background: transparent;
  color: #8b949e;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.tab-btn:hover { color: #c9d1d9; background: rgba(255,255,255,0.05); }
.tab-btn.active { color: #58a6ff; background: rgba(88,166,255,0.1); border-color: rgba(88,166,255,0.3); }

.back-link {
  margin-left: auto;
  color: #8b949e;
  text-decoration: none;
  font-size: 0.9rem;
}

.back-link:hover { color: #58a6ff; }

/* ===== Tab 内容 ===== */
.tab-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px;
}

/* ===== 卡片 ===== */
.card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 20px 24px;
  margin-bottom: 20px;
}

.card h3 { margin: 0 0 16px; font-size: 1.05rem; }
.card h4 { margin: 0 0 10px; font-size: 0.95rem; }

/* ===== 表单 ===== */
.input, select {
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #0d1117;
  color: #c9d1d9;
  font-size: 0.9rem;
  outline: none;
  width: 100%;
  box-sizing: border-box;
}

.input:focus, select:focus { border-color: #58a6ff; }

select option { background: #161b22; color: #c9d1d9; }

textarea.input { resize: vertical; font-family: inherit; }

.input-group { margin-bottom: 12px; }
.input-group label { display: block; font-size: 0.82rem; margin-bottom: 4px; color: #8b949e; }

/* ===== 按钮 ===== */
.btn {
  padding: 8px 16px;
  border-radius: 6px;
  border: 1px solid #30363d;
  background: #21262d;
  color: #c9d1d9;
  cursor: pointer;
  font-size: 0.88rem;
  transition: all 0.15s;
}
.btn:hover { background: #30363d; }
.btn:disabled { opacity: 0.5; cursor: default; }

.btn-primary { background: #238636; border-color: #2ea043; color: white; }
.btn-primary:hover { background: #2ea043; }

.btn-secondary { background: #30363d; }

.btn-sm { padding: 5px 12px; font-size: 0.82rem; }

.btn-delete-danger { background: #da3633; border-color: #f85149; color: white; }
.btn-delete-danger:hover { background: #f85149; }

.btn-icon { background: none; border: none; cursor: pointer; font-size: 1rem; padding: 2px 4px; }

/* ===== 用户管理 ===== */
.lookup-row { display: flex; gap: 0.75rem; }
.lookup-row .input { flex: 1; max-width: 400px; }

.user-detail { padding: 0.5rem 0; }
.stat-item { display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid #21262d; }
.stat-label { font-weight: 600; color: #c9d1d9; }
.stat-value { color: #8b949e; }

.actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 16px; margin-top: 16px; }
.action-card { padding: 16px; border: 1px solid #30363d; border-radius: 8px; background: #0d1117; }
.action-row { display: flex; gap: 0.75rem; align-items: center; }

/* ===== 小说/时间线布局 ===== */
.novel-layout { display: grid; grid-template-columns: 1fr 1.5fr; gap: 20px; }

.novel-list, .timeline-panel {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  padding: 16px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid #21262d;
}
.section-header h3, .section-header h4 { margin: 0; font-size: 1rem; }

.novel-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.novel-item:hover { background: #21262d; }
.novel-item.active { background: rgba(88,166,255,0.1); border: 1px solid rgba(88,166,255,0.3); }

.novel-sort {
  font-size: 0.75rem;
  color: #58a6ff;
  background: rgba(88,166,255,0.1);
  padding: 1px 6px;
  border-radius: 4px;
  min-width: 22px;
  text-align: center;
}
.novel-name { font-weight: 600; flex: 1; }
.novel-meta { font-size: 0.82rem; color: #8b949e; }
.novel-actions { display: flex; gap: 4px; opacity: 0.3; transition: opacity 0.15s; }
.novel-item:hover .novel-actions { opacity: 1; }

.timeline-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #21262d;
}
.timeline-item:last-child { border-bottom: none; }

.tl-info { display: flex; flex-direction: column; gap: 2px; }
.tl-desc { font-size: 0.82rem; color: #8b949e; }
.tl-sort { font-size: 0.78rem; color: #484f58; }
.tl-actions { display: flex; gap: 4px; }

/* ===== 角色管理 ===== */
.char-toolbar { display: flex; gap: 10px; margin-bottom: 20px; align-items: center; flex-wrap: wrap; }

.char-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 12px;
}

.char-main { display: flex; justify-content: space-between; align-items: flex-start; }

.char-info { display: flex; flex-direction: column; gap: 4px; }
.char-info strong { font-size: 1.05rem; }
.char-novel { font-size: 0.82rem; color: #8b949e; }

.char-bg { margin-top: 8px; font-size: 0.85rem; color: #8b949e; }

.char-timelines { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.tl-tag { padding: 2px 10px; background: rgba(88,166,255,0.12); border-radius: 12px; font-size: 0.78rem; color: #58a6ff; }

.char-actions { display: flex; gap: 6px; }

.char-form-grid { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }

.char-timelines-editor { margin-top: 16px; }

.tl-entry {
  border: 1px solid #30363d;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 10px;
  background: #0d1117;
}

.tl-entry-row { display: flex; gap: 8px; margin-bottom: 8px; align-items: center; }

/* ===== 弹窗 ===== */
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
  padding: 20px;
}

.modal-card {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 12px;
  padding: 24px 28px;
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  overflow-y: auto;
}

.modal-sm { max-width: 400px; }
.modal-lg { max-width: 700px; }

.modal-card h3 { margin: 0 0 16px; font-size: 1.1rem; }
.modal-card p { color: #8b949e; margin-bottom: 16px; }

.modal-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

/* ===== Toast ===== */
.toast {
  position: fixed;
  top: 80px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 300;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 0.9rem;
  animation: fadeIn 0.2s;
}

.toast-success { background: #238636; color: white; }
.toast-error { background: #da3633; color: white; }

@keyframes fadeIn { from { opacity: 0; transform: translateX(-50%) translateY(-8px); } to { opacity: 1; transform: translateX(-50%) translateY(0); } }

/* ===== 工具类 ===== */
.error-message {
  padding: 0.7rem 1rem;
  background: rgba(248,81,73,0.15);
  border: 1px solid rgba(248,81,73,0.3);
  color: #f85149;
  border-radius: 6px;
  margin-bottom: 12px;
  font-size: 0.85rem;
}

.text-muted { color: #8b949e; }
.badge { padding: 2px 8px; border-radius: 10px; font-size: 0.78rem; background: #21262d; color: #8b949e; }
.badge-success { background: rgba(35,134,54,0.2); color: #3fb950; }

/* ===== 响应式 ===== */
@media (max-width: 768px) {
  .top-bar { flex-wrap: wrap; gap: 0.75rem; padding: 12px 16px; }
  .top-bar h1 { font-size: 1rem; }
  .tab-btn { font-size: 0.8rem; padding: 5px 12px; }
  .tab-content { padding: 12px; }
  .novel-layout { grid-template-columns: 1fr; }
  .char-form-grid { grid-template-columns: 1fr 1fr; }
  .gate-card { padding: 2rem 1.5rem; }
}
</style>
