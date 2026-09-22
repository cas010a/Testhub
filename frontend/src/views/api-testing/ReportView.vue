<template>
  <div class="report-view">
    <div class="header">
      <h3>{{ $t('apiTesting.report.title') }}</h3>
      <div class="actions">
        <el-button type="primary" @click="refreshReports">{{ $t('apiTesting.report.refreshReport') }}</el-button>
        <el-button @click="openAllureReport">{{ $t('apiTesting.report.viewAllureReport') }}</el-button>
      </div>
    </div>

    <div class="content">
      <el-table :data="reports" v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="test_suite_name" :label="$t('apiTesting.report.testSuite')" min-width="200" />
        <el-table-column prop="status" :label="$t('apiTesting.common.status')" width="120">
          <template #default="scope">
            <el-tag :type="getStatusType(scope.row.status)">
              {{ getStatusText(scope.row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="total_requests" :label="$t('apiTesting.report.totalRequests')" width="100" />
        <el-table-column prop="passed_requests" :label="$t('apiTesting.report.passedCount')" width="100">
          <template #default="scope">
            <span style="color: #67c23a">{{ scope.row.passed_requests }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="failed_requests" :label="$t('apiTesting.report.failedCount')" width="100">
          <template #default="scope">
            <span style="color: #f56c6c">{{ scope.row.failed_requests }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="executed_by.username" :label="$t('apiTesting.report.executor')" width="120" />
        <el-table-column prop="created_at" :label="$t('apiTesting.report.executionTime')" width="180">
          <template #default="scope">
            {{ formatDate(scope.row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="$t('apiTesting.common.operation')" width="220">
          <template #default="scope">
            <el-button link type="primary" @click="viewReportDetail(scope.row)">{{ $t('apiTesting.report.generateAndViewReport') }}</el-button>
            <el-button link type="primary" @click="openExecutionDetail(scope.row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 执行详情弹窗：展示每个接口的入参/出参 -->
    <el-dialog v-model="detailVisible" :title="detailTitle" width="78%" top="4vh" destroy-on-close>
      <div v-loading="detailLoading" class="detail-content">
        <template v-if="detailResults && detailResults.length">
          <el-collapse v-model="activeDetail">
            <el-collapse-item v-for="(item, idx) in detailResults" :key="idx" :name="idx">
              <template #title>
                <div class="detail-title">
                  <el-tag size="small" :type="item.passed ? 'success' : 'danger'">
                    {{ item.passed ? '通过' : '失败' }}
                  </el-tag>
                  <span class="detail-name">{{ item.method }} {{ item.name }}</span>
                  <span class="detail-url">{{ item.url }}</span>
                  <span v-if="item.response_time" class="detail-time">{{ item.response_time.toFixed ? item.response_time.toFixed(0) : item.response_time }}ms</span>
                </div>
              </template>
              <div v-if="item.error" class="detail-error">错误：{{ item.error }}</div>
              <div class="detail-block">
                <h4>入参（Request）</h4>
                <pre>{{ formatJson(item.request_data) }}</pre>
              </div>
              <div class="detail-block">
                <h4>出参（Response）</h4>
                <pre>{{ formatJson(item.response_data) }}</pre>
              </div>
              <div v-if="item.extracted_variables && Object.keys(item.extracted_variables).length" class="detail-block">
                <h4>提取变量</h4>
                <pre>{{ formatJson(item.extracted_variables) }}</pre>
              </div>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-empty v-else description="该执行记录暂无详情数据，请重新运行测试套件后查看" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import api from '@/utils/api'
import dayjs from 'dayjs'

const { t } = useI18n()
const reports = ref([])
const loading = ref(false)

const detailVisible = ref(false)
const detailLoading = ref(false)
const detailResults = ref([])
const detailTitle = ref('')
const activeDetail = ref([])

const loadReports = async () => {
  loading.value = true
  try {
    const response = await api.get('/api-testing/test-executions/')
    reports.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.loadReports'))
  } finally {
    loading.value = false
  }
}

const refreshReports = async () => {
  await loadReports()
}

const generateAndOpenAllureReport = async (executionId) => {
  try {
    // 调用API生成Allure报告数据
    const response = await api.post(`/api-testing/test-executions/${executionId}/generate-allure-report/`)
    ElMessage.success(t('apiTesting.messages.success.reportGenerated'))

    // 通过当前窗口的origin构造完整的URL，确保通过Vite代理访问
    const fullUrl = `${window.location.origin}${response.data.report_url}`;
    window.open(fullUrl, '_blank')
  } catch (error) {
    ElMessage.error(t('apiTesting.messages.error.reportGenerateFailed'))
  }
}

const openAllureReport = () => {
  // 提示用户需要先选择一个执行记录来生成报告
  ElMessage.info(t('apiTesting.report.selectExecutionTip'))
}

const viewReportDetail = (report) => {
  // 生成并打开Allure报告
  generateAndOpenAllureReport(report.id)
}

// 打开执行详情弹窗：展示每个接口的入参/出参
const openExecutionDetail = async (report) => {
  detailVisible.value = true
  detailLoading.value = true
  detailResults.value = []
  activeDetail.value = []
  detailTitle.value = `执行详情 - ${report.test_suite_name || report.id}`
  try {
    const response = await api.get(`/api-testing/test-executions/${report.id}/`)
    const results = response.data.results
    if (Array.isArray(results)) {
      detailResults.value = results
      // 默认展开第一条
      if (results.length) activeDetail.value = [0]
    } else {
      detailResults.value = []
    }
  } catch (error) {
    ElMessage.error('加载执行详情失败')
    console.error('加载执行详情失败:', error)
  } finally {
    detailLoading.value = false
  }
}

// 格式化JSON展示（友好的缩进，出错时兜底）
const formatJson = (obj) => {
  if (obj === null || obj === undefined || obj === '') return '（无）'
  if (typeof obj === 'string') {
    try {
      return JSON.stringify(JSON.parse(obj), null, 2)
    } catch (e) {
      return obj
    }
  }
  try {
    return JSON.stringify(obj, null, 2)
  } catch (e) {
    return String(obj)
  }
}

const getStatusType = (status) => {
  const typeMap = {
    'PENDING': 'info',
    'RUNNING': 'warning',
    'COMPLETED': 'success',
    'FAILED': 'danger',
    'CANCELLED': 'info'
  }
  return typeMap[status] || 'info'
}

const getStatusText = (status) => {
  const statusKey = {
    'PENDING': 'pending',
    'RUNNING': 'running',
    'COMPLETED': 'completed',
    'FAILED': 'failed',
    'CANCELLED': 'cancelled'
  }[status]
  return statusKey ? t(`apiTesting.report.status.${statusKey}`) : status
}

const formatDate = (dateString) => {
  return dayjs(dateString).format('YYYY-MM-DD HH:mm:ss')
}

onMounted(() => {
  loadReports()
})
</script>

<style scoped>
.report-view {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header h3 {
  margin: 0;
  color: #303133;
}

.content {
  flex: 1;
  overflow: auto;
}

.detail-content {
  max-height: 70vh;
  overflow: auto;
}

.detail-title {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  overflow: hidden;
}

.detail-name {
  font-weight: 600;
  white-space: nowrap;
}

.detail-url {
  color: #909399;
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-time {
  color: #909399;
  font-size: 12px;
  margin-left: auto;
  white-space: nowrap;
}

.detail-error {
  color: #f56c6c;
  background: #fef0f0;
  padding: 8px 12px;
  border-radius: 4px;
  margin-bottom: 12px;
  font-size: 13px;
}

.detail-block h4 {
  margin: 0 0 8px;
  color: #303133;
  font-size: 13px;
}

.detail-block pre {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  overflow: auto;
  max-height: 320px;
  margin: 0 0 16px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
