<template>
  <div class="user-manage-container">
    <!-- 头部 -->
    <div class="page-header">
      <div class="header-left">
        <h2 class="page-title">{{ $t('userManage.title') }}</h2>
        <p class="page-desc">{{ $t('userManage.subtitle') }}</p>
      </div>
      <div class="header-right">
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ $t('userManage.addUser') }}</el-button>
      </div>
    </div>

    <!-- 搜索栏 -->
    <div class="filter-bar">
      <el-input
        v-model="searchKeyword"
        :placeholder="$t('userManage.searchPlaceholder')"
        clearable
        style="width: 300px"
        @keyup.enter="loadUsers"
        @clear="loadUsers"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" plain :icon="Search" @click="loadUsers">{{ $t('common.search') }}</el-button>
      <el-button :icon="Refresh" @click="resetAndReload">{{ $t('common.reset') }}</el-button>
    </div>

    <!-- 用户表格 -->
    <el-card shadow="never" class="table-card">
      <el-table
        v-loading="loading"
        :data="users"
        stripe
        style="width: 100%"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="username" :label="$t('userManage.username')" min-width="120">
          <template #default="{ row }">
            <span>{{ row.username }}</span>
            <el-tag v-if="row.is_superuser" size="small" type="danger" effect="plain" class="role-extra-tag">
              {{ $t('userManage.superAdmin') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="email" :label="$t('userManage.email')" min-width="180">
          <template #default="{ row }">
            <span v-if="row.email">{{ row.email }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userManage.name')" min-width="100">
          <template #default="{ row }">
            <span>{{ row.first_name || row.last_name ? `${row.first_name} ${row.last_name}`.trim() : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="phone" :label="$t('userManage.phone')" min-width="120">
          <template #default="{ row }">
            <span v-if="row.phone">{{ row.phone }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="department" :label="$t('userManage.department')" min-width="110">
          <template #default="{ row }">
            <span v-if="row.department">{{ row.department }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="position" :label="$t('userManage.position')" min-width="110">
          <template #default="{ row }">
            <span v-if="row.position">{{ row.position }}</span>
            <span v-else class="empty-text">-</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userManage.role')" width="110" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_staff" type="warning" size="small">{{ $t('userManage.adminRole') }}</el-tag>
            <el-tag v-else type="info" size="small">{{ $t('userManage.userRole') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userManage.status')" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'danger'" size="small">
              {{ row.is_active ? $t('userManage.enabled') : $t('userManage.disabled') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userManage.createdAt')" width="170">
          <template #default="{ row }">
            <span class="time-text">{{ formatTime(row.date_joined) }}</span>
          </template>
        </el-table-column>
        <el-table-column :label="$t('userManage.actions')" width="230" align="center" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)">{{ $t('userManage.edit') }}</el-button>
            <el-button link type="warning" size="small" @click="openResetPassword(row)">{{ $t('userManage.resetPassword') }}</el-button>
            <el-button
              v-if="row.id !== currentUserId"
              link
              :type="row.is_active ? 'danger' : 'success'"
              size="small"
              @click="toggleActive(row)"
            >
              {{ row.is_active ? $t('userManage.disable') : $t('userManage.enable') }}
            </el-button>
            <el-button
              v-if="row.id !== currentUserId && !row.is_superuser"
              link
              type="danger"
              size="small"
              @click="handleDelete(row)"
            >
              {{ $t('userManage.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </el-card>

    <!-- 新增 / 编辑用户对话框 -->
    <el-dialog
      v-model="formDialogVisible"
      :title="isEdit ? $t('userManage.editUser') : $t('userManage.addUser')"
      width="560px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="formRules" label-width="90px">
        <el-form-item :label="$t('userManage.username')" prop="username">
          <el-input v-model="form.username" :disabled="isEdit" :placeholder="$t('userManage.usernamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.email')" prop="email">
          <el-input v-model="form.email" :placeholder="$t('userManage.emailPlaceholder')" />
        </el-form-item>
        <el-form-item v-if="!isEdit" :label="$t('userManage.password')" prop="password">
          <el-input v-model="form.password" type="password" show-password :placeholder="$t('userManage.passwordPlaceholder')" />
        </el-form-item>
        <el-form-item v-if="!isEdit" :label="$t('userManage.confirmPassword')" prop="password_confirm">
          <el-input v-model="form.password_confirm" type="password" show-password :placeholder="$t('userManage.confirmPasswordPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.name')">
          <el-input v-model="form.first_name" :placeholder="$t('userManage.namePlaceholder')" style="width: 200px" />
          <el-input v-model="form.last_name" :placeholder="$t('userManage.lastName')" style="width: 200px; margin-left: 10px" />
        </el-form-item>
        <el-form-item :label="$t('userManage.phone')">
          <el-input v-model="form.phone" :placeholder="$t('userManage.phonePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.department')">
          <el-input v-model="form.department" :placeholder="$t('userManage.departmentPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.position')">
          <el-input v-model="form.position" :placeholder="$t('userManage.positionPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.role')">
          <el-switch
            v-model="form.is_staff"
            :active-text="$t('userManage.adminRole')"
            :inactive-text="$t('userManage.userRole')"
          />
        </el-form-item>
        <el-form-item v-if="isEdit" :label="$t('userManage.status')">
          <el-switch
            v-model="form.is_active"
            active-text="启用"
            inactive-text="禁用"
            :active-value="true"
            :inactive-value="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- 重置密码对话框 -->
    <el-dialog
      v-model="passwordDialogVisible"
      :title="$t('userManage.resetPassword')"
      width="420px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
        <el-form-item :label="$t('userManage.newPassword')" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password :placeholder="$t('userManage.passwordPlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('userManage.confirmPassword')" prop="password_confirm">
          <el-input v-model="pwdForm.password_confirm" type="password" show-password :placeholder="$t('userManage.confirmPasswordPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="savingPassword" @click="submitResetPassword">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { getUserManageList, createUser, updateUser, deleteUser } from '@/api/users'
import { useUserStore } from '@/stores/user'

const { t } = useI18n()
const userStore = useUserStore()
const currentUserId = computed(() => userStore.user?.id)

const loading = ref(false)
const users = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const searchKeyword = ref('')

// 新增/编辑
const formDialogVisible = ref(false)
const isEdit = ref(false)
const saving = ref(false)
const formRef = ref(null)
const editId = ref(null)
const form = ref({
  username: '',
  email: '',
  password: '',
  password_confirm: '',
  first_name: '',
  last_name: '',
  phone: '',
  department: '',
  position: '',
  is_staff: false,
  is_active: true
})

// 重置密码
const passwordDialogVisible = ref(false)
const savingPassword = ref(false)
const pwdFormRef = ref(null)
const resetTarget = ref(null)
const pwdForm = ref({ password: '', password_confirm: '' })

const formRules = {
  username: [{ required: true, message: t('userManage.usernameRequired'), trigger: 'blur' }],
  password: [{ required: true, message: t('userManage.passwordRequired'), trigger: 'blur' }],
  password_confirm: [{
    validator: (rule, value, callback) => {
      if (!value) callback(new Error(t('userManage.confirmPasswordRequired')))
      else if (value !== form.value.password) callback(new Error(t('userManage.passwordMismatch')))
      else callback()
    },
    trigger: 'blur'
  }]
}

const pwdRules = {
  password: [{ required: true, message: t('userManage.passwordRequired'), trigger: 'blur' }],
  password_confirm: [{
    validator: (rule, value, callback) => {
      if (!value) callback(new Error(t('userManage.confirmPasswordRequired')))
      else if (value !== pwdForm.value.password) callback(new Error(t('userManage.passwordMismatch')))
      else callback()
    },
    trigger: 'blur'
  }]
}

const loadUsers = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (searchKeyword.value.trim()) {
      params.search = searchKeyword.value.trim()
    }
    const response = await getUserManageList(params)
    const data = response.data
    if (Array.isArray(data)) {
      users.value = data
      total.value = data.length
    } else {
      users.value = data.results || []
      total.value = data.count || 0
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('userManage.loadFailed'))
  } finally {
    loading.value = false
  }
}

const resetAndReload = () => {
  searchKeyword.value = ''
  page.value = 1
  loadUsers()
}

const openCreate = () => {
  isEdit.value = false
  editId.value = null
  form.value = {
    username: '', email: '', password: '', password_confirm: '',
    first_name: '', last_name: '', phone: '', department: '', position: '',
    is_staff: false, is_active: true
  }
  formDialogVisible.value = true
}

const openEdit = (row) => {
  isEdit.value = true
  editId.value = row.id
  form.value = {
    username: row.username,
    email: row.email || '',
    password: '',
    password_confirm: '',
    first_name: row.first_name || '',
    last_name: row.last_name || '',
    phone: row.phone || '',
    department: row.department || '',
    position: row.position || '',
    is_staff: row.is_staff,
    is_active: row.is_active
  }
  formDialogVisible.value = true
}

const submitForm = async () => {
  try {
    await formRef.value.validate()
  } catch {
    return
  }
  saving.value = true
  try {
    const payload = {
      username: form.value.username,
      email: form.value.email,
      first_name: form.value.first_name,
      last_name: form.value.last_name,
      phone: form.value.phone,
      department: form.value.department,
      position: form.value.position,
      is_staff: form.value.is_staff,
      is_active: form.value.is_active
    }
    if (isEdit.value) {
      await updateUser(editId.value, payload)
      ElMessage.success(t('userManage.updateSuccess'))
    } else {
      payload.password = form.value.password
      payload.password_confirm = form.value.password_confirm
      await createUser(payload)
      ElMessage.success(t('userManage.createSuccess'))
    }
    formDialogVisible.value = false
    loadUsers()
  } catch (error) {
    const detail = error.response?.data
    const msg = typeof detail === 'string' ? detail
      : (detail && (detail.detail || detail.username?.[0] || detail.password?.[0] || detail.email?.[0])) || t('userManage.saveFailed')
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const openResetPassword = (row) => {
  resetTarget.value = row
  pwdForm.value = { password: '', password_confirm: '' }
  passwordDialogVisible.value = true
}

const submitResetPassword = async () => {
  try {
    await pwdFormRef.value.validate()
  } catch {
    return
  }
  savingPassword.value = true
  try {
    await updateUser(resetTarget.value.id, {
      password: pwdForm.value.password,
      password_confirm: pwdForm.value.password_confirm
    })
    ElMessage.success(t('userManage.resetPasswordSuccess'))
    passwordDialogVisible.value = false
  } catch (error) {
    const detail = error.response?.data
    const msg = typeof detail === 'string' ? detail : (detail?.detail || detail?.password?.[0]) || t('userManage.saveFailed')
    ElMessage.error(msg)
  } finally {
    savingPassword.value = false
  }
}

const toggleActive = async (row) => {
  const action = row.is_active ? t('userManage.disable') : t('userManage.enable')
  try {
    await ElMessageBox.confirm(
      t('userManage.toggleConfirm', { action, username: row.username }),
      t('common.tips'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await updateUser(row.id, { is_active: !row.is_active })
    ElMessage.success(t('userManage.toggleSuccess', { action }))
    loadUsers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || t('userManage.saveFailed'))
  }
}

const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      t('userManage.deleteConfirm', { username: row.username }),
      t('common.tips'),
      { confirmButtonText: t('common.confirm'), cancelButtonText: t('common.cancel'), type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await deleteUser(row.id)
    ElMessage.success(t('userManage.deleteSuccess'))
    loadUsers()
  } catch (error) {
    const detail = error.response?.data
    ElMessage.error(typeof detail === 'string' ? detail : (detail?.detail || t('userManage.saveFailed')))
  }
}

const formatTime = (val) => {
  if (!val) return '-'
  const d = new Date(val)
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped lang="scss">
.user-manage-container {
  padding: 20px;
  min-height: 100vh;
  background: #f5f7fa;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;

  .page-title {
    margin: 0 0 4px;
    font-size: 22px;
    font-weight: 600;
    color: #1f2d3d;
  }

  .page-desc {
    margin: 0;
    font-size: 13px;
    color: #8a939d;
  }
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.table-card {
  border-radius: 8px;

  .empty-text {
    color: #c0c4cc;
  }

  .role-extra-tag {
    margin-left: 6px;
  }

  .time-text {
    color: #606266;
    font-size: 13px;
  }
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
