<template>
  <div class="script-recorder">
    <!-- 页面标题 -->
    <div class="page-header">
      <h3>{{ $t('appAutomation.recorder.title') }}</h3>
      <div class="header-actions">
        <el-button size="small" :icon="Refresh" :loading="loading" @click="loadAll">
          {{ $t('appAutomation.common.refresh') }}
        </el-button>
        <el-button size="small" :icon="Connection" @click="discoverDevices">
          {{ $t('appAutomation.recorder.discoverDevices') }}
        </el-button>
      </div>
    </div>

    <el-row :gutter="16">
      <!-- 左：设备画面 -->
      <el-col :xs="24" :md="14">
        <el-card shadow="never" class="recorder-card">
          <template #header>
            <div class="card-header">
              <span>{{ $t('appAutomation.recorder.deviceScreen') }}</span>
              <div class="card-header-right">
                <el-select
                  v-model="selectedDeviceId"
                  :placeholder="$t('appAutomation.recorder.selectDevicePlaceholder')"
                  size="small"
                  filterable
                  style="width: 220px"
                  :loading="devicesLoading"
                  @change="handleDeviceChange"
                >
                  <el-option
                    v-for="device in devices"
                    :key="device.id"
                    :label="`${device.name || device.device_id} (${device.status})`"
                    :value="device.id"
                  />
                </el-select>
                <el-button size="small" :icon="Camera" :loading="capturing" :disabled="!selectedDeviceId" @click="captureScreen">
                  {{ $t('appAutomation.recorder.capture') }}
                </el-button>
                <el-switch
                  v-model="autoRefresh"
                  :active-text="$t('appAutomation.recorder.autoRefresh')"
                  size="small"
                  style="margin-left: 8px"
                  @change="handleAutoRefreshChange"
                />
              </div>
            </div>
          </template>

          <!-- 截图画面 -->
          <div class="screen-area">
            <div
              v-if="screenshot"
              ref="imageWrapper"
              class="screen-wrapper"
              :class="{ recording: recording }"
              @mousedown="handleMouseDown"
              @mousemove="handleMouseMove"
              @mouseup="handleMouseUp"
              @mouseleave="handleMouseUp"
            >
              <img
                ref="imageRef"
                :src="screenshot"
                class="screen-image"
                draggable="false"
                @load="handleImageLoad"
              />
              <!-- 拖拽框选 -->
              <div v-if="selection" class="selection-box" :style="selectionStyle"></div>
              <!-- 录制中标识 -->
              <div v-if="recording" class="recording-badge">
                <span class="rec-dot"></span>{{ $t('appAutomation.recorder.recording') }}
              </div>
            </div>
            <div v-else class="screen-empty">
              <el-empty :description="$t('appAutomation.recorder.screenEmptyTip')">
                <el-button type="primary" size="small" :disabled="!selectedDeviceId" @click="captureScreen">
                  {{ $t('appAutomation.recorder.captureFirst') }}
                </el-button>
              </el-empty>
            </div>
          </div>

          <!-- 操作提示 -->
          <div class="screen-tip">
            <el-tag size="small" effect="plain">{{ $t('appAutomation.recorder.tipClick') }}</el-tag>
            <el-tag size="small" effect="plain" type="success">{{ $t('appAutomation.recorder.tipDrag') }}</el-tag>
            <el-tag size="small" effect="plain" type="warning">{{ $t('appAutomation.recorder.tipOnlyRecordWhenStarted') }}</el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- 右：录制控制与步骤 -->
      <el-col :xs="24" :md="10">
        <el-card shadow="never" class="recorder-card">
          <template #header>
            <div class="card-header">
              <span>{{ $t('appAutomation.recorder.recordControl') }}</span>
            </div>
          </template>

          <!-- 录制控制条 -->
          <div class="control-bar">
            <el-button
              v-if="!recording"
              type="danger"
              :icon="VideoPlay"
              :disabled="!selectedDeviceId"
              @click="startRecording"
            >
              {{ $t('appAutomation.recorder.start') }}
            </el-button>
            <el-button v-else type="warning" :icon="VideoPause" @click="stopRecording">
              {{ $t('appAutomation.recorder.stop') }}
            </el-button>
            <el-button :icon="Delete" :disabled="steps.length === 0" @click="clearSteps">
              {{ $t('appAutomation.recorder.clear') }}
            </el-button>
            <el-switch
              v-model="syncToDevice"
              :active-text="$t('appAutomation.recorder.syncToDevice')"
              size="small"
              style="margin-left: auto"
            />
          </div>

          <!-- 操作模式 -->
          <div class="mode-bar">
            <span class="mode-label">{{ $t('appAutomation.recorder.clickMode') }}:</span>
            <el-radio-group v-model="activeAction" size="small">
              <el-radio-button value="click">{{ $t('appAutomation.recorder.modeClick') }}</el-radio-button>
              <el-radio-button value="long_press">{{ $t('appAutomation.recorder.modeLongPress') }}</el-radio-button>
            </el-radio-group>
            <span class="mode-label" style="margin-left: 12px">{{ $t('appAutomation.recorder.longPressDuration') }}:</span>
            <el-input-number v-model="longPressDuration" :min="1" :max="10" :step="0.5" size="small" style="width: 90px" />
          </div>

          <!-- 输入文本面板 -->
          <div class="input-panel">
            <div class="input-row">
              <el-input
                v-model="pendingText"
                size="small"
                :placeholder="$t('appAutomation.recorder.textPlaceholder')"
                clearable
                @keyup.enter="commitTextStep"
              />
              <el-button size="small" type="primary" :disabled="!pendingText" @click="commitTextStep">
                {{ $t('appAutomation.recorder.addInput') }}
              </el-button>
            </div>
            <div class="input-tip">
              <el-checkbox v-model="textNeedsPoint" size="small">
                {{ $t('appAutomation.recorder.textNeedsPointTip') }}
              </el-checkbox>
              <span v-if="textPoint" class="text-point-info">{{ $t('appAutomation.recorder.textPointSelected', { point: textPoint }) }}</span>
              <el-button v-if="textPoint" link size="small" @click="textPoint = ''">{{ $t('appAutomation.common.clear') }}</el-button>
            </div>
          </div>

          <!-- 手动添加 -->
          <div class="add-bar">
            <span class="mode-label">{{ $t('appAutomation.recorder.addStep') }}:</span>
            <el-button size="small" :icon="Timer" @click="addWaitStep">
              {{ $t('appAutomation.recorder.addWait') }}
            </el-button>
            <el-button size="small" :icon="Key" @click="addKeyeventStep">
              {{ $t('appAutomation.recorder.addKey') }}
            </el-button>
          </div>

          <el-divider style="margin: 12px 0" />

          <!-- 步骤列表 -->
          <div class="steps-header">
            <span>{{ $t('appAutomation.recorder.recordedSteps') }} ({{ steps.length }})</span>
            <el-button
              type="primary"
              size="small"
              :icon="Check"
              :disabled="steps.length === 0"
              @click="openSaveDialog"
            >
              {{ $t('appAutomation.recorder.saveAsCase') }}
            </el-button>
            <el-button
              size="small"
              :icon="Download"
              :disabled="steps.length === 0"
              @click="openExportDialog"
            >
              {{ $t('appAutomation.recorder.exportScript') }}
            </el-button>
          </div>

          <div v-if="steps.length === 0" class="steps-empty">
            <el-empty :image-size="60" :description="$t('appAutomation.recorder.noSteps')" />
          </div>
          <div v-else class="steps-list">
            <div v-for="(step, index) in steps" :key="index" class="step-item" :class="{ active: index === activeStepIndex }">
              <span class="step-index">{{ index + 1 }}</span>
              <span class="step-type" :class="`type-${step.type}`">{{ stepTypeLabel(step.type) }}</span>
              <span class="step-name" :title="step.name">{{ step.name }}</span>
              <span class="step-actions">
                <el-button link size="small" :icon="Top" :disabled="index === 0" @click="moveStep(index, -1)" />
                <el-button link size="small" :icon="Bottom" :disabled="index === steps.length - 1" @click="moveStep(index, 1)" />
                <el-button link size="small" type="danger" :icon="Delete" @click="removeStep(index)" />
              </span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 保存为测试用例对话框 -->
    <el-dialog
      v-model="saveDialogVisible"
      :title="$t('appAutomation.recorder.saveDialogTitle')"
      width="480px"
      :close-on-click-modal="false"
    >
      <el-form :model="saveForm" label-width="90px" size="small">
        <el-form-item :label="$t('appAutomation.recorder.caseName')" required>
          <el-input v-model.trim="saveForm.name" :placeholder="$t('appAutomation.recorder.caseNamePlaceholder')" />
        </el-form-item>
        <el-form-item :label="$t('appAutomation.common.project')">
          <el-select v-model="saveForm.project" clearable filterable style="width: 100%" :placeholder="$t('appAutomation.common.selectProject')">
            <el-option v-for="proj in projectList" :key="proj.id" :label="proj.name" :value="proj.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('appAutomation.common.description')">
          <el-input v-model="saveForm.description" type="textarea" :rows="3" :placeholder="$t('appAutomation.recorder.caseDescPlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button size="small" @click="saveDialogVisible = false">{{ $t('appAutomation.common.cancel') }}</el-button>
        <el-button size="small" type="primary" :loading="saving" :disabled="!saveForm.name" @click="saveAsCase">
          {{ $t('appAutomation.common.save') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 导出 Airtest 脚本对话框 -->
    <el-dialog
      v-model="exportDialogVisible"
      :title="$t('appAutomation.recorder.exportDialogTitle')"
      width="720px"
      :close-on-click-modal="false"
    >
      <div class="export-tip">
        {{ $t('appAutomation.recorder.exportTip') }}
      </div>
      <el-input
        :model-value="airtestScript"
        type="textarea"
        :rows="14"
        readonly
        class="export-code"
      />
      <template #footer>
        <el-button size="small" @click="exportDialogVisible = false">{{ $t('appAutomation.common.close') }}</el-button>
        <el-button size="small" type="primary" :icon="Download" @click="downloadScript">
          {{ $t('appAutomation.recorder.downloadPy') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Connection, Camera, VideoPlay, VideoPause, Delete, Download, Check, Timer, Key, Top, Bottom } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

import {
  getDeviceList,
  captureDeviceScreenshot,
  discoverDevices,
  getAppProjects,
  createTestCase
} from '@/api/app-automation'
import { sendDeviceAction } from '@/api/app-automation'

const { t } = useI18n()

// ========== 设备 ==========
const devices = ref([])
const devicesLoading = ref(false)
const selectedDeviceId = ref(null)
const loading = ref(false)
const screenshot = ref('')
const capturing = ref(false)

// 截图相关
const imageWrapper = ref(null)
const imageRef = ref(null)
const displayWidth = ref(0)
const displayHeight = ref(0)
const deviceWidth = ref(0)
const deviceHeight = ref(0)
const imageOffsetX = ref(0)
const imageOffsetY = ref(0)

// 选区
const selection = ref(null)
const dragStart = ref(null)
const mouseDown = ref(false)

// 录制状态
const recording = ref(false)
const syncToDevice = ref(true)
const autoRefresh = ref(false)
let refreshTimer = null

// 操作模式
const activeAction = ref('click')
const longPressDuration = ref(2)
const steps = ref([])
const activeStepIndex = ref(null)

// 输入面板
const pendingText = ref('')
const textNeedsPoint = ref(true)
const textPoint = ref('')

// 保存
const saveDialogVisible = ref(false)
const saving = ref(false)
const saveForm = ref({ name: '', project: null, description: '' })
const projectList = ref([])

// 导出
const exportDialogVisible = ref(false)

// ========== 计算属性 ==========
const selectionStyle = computed(() => {
  if (!selection.value) return {}
  return {
    left: `${selection.value.x}px`,
    top: `${selection.value.y}px`,
    width: `${selection.value.w}px`,
    height: `${selection.value.h}px`
  }
})

const airtestScript = computed(() => generateAirtestScript())

// ========== 生命周期 ==========
onMounted(() => {
  loadAll()
})

onBeforeUnmount(() => {
  stopAutoRefresh()
})

// ========== 数据加载 ==========
const loadAll = async () => {
  loading.value = true
  try {
    await Promise.all([loadDevices(), loadProjects()])
  } finally {
    loading.value = false
  }
}

const loadDevices = async () => {
  devicesLoading.value = true
  try {
    const res = await getDeviceList({ page_size: 100 })
    const data = res.data || res
    devices.value = (data.results || data || []).filter(d => d.status !== 'offline')
    if (devices.value.length > 0 && !selectedDeviceId.value) {
      selectedDeviceId.value = devices.value[0].id
      captureScreen()
    } else if (selectedDeviceId.value) {
      const stillExists = devices.value.some(d => d.id === selectedDeviceId.value)
      if (!stillExists) {
        selectedDeviceId.value = devices.value.length > 0 ? devices.value[0].id : null
      }
    }
  } catch (e) {
    ElMessage.error(t('appAutomation.recorder.loadDevicesFailed'))
  } finally {
    devicesLoading.value = false
  }
}

const loadProjects = async () => {
  try {
    const res = await getAppProjects({ page_size: 100 })
    const data = res.data || res
    projectList.value = data.results || data || []
  } catch (e) {
    // 项目加载失败不阻塞录制
  }
}

const discoverDeviceList = async () => {
  try {
    await discoverDevices()
    await loadDevices()
    ElMessage.success(t('appAutomation.recorder.discoverSuccess'))
  } catch (e) {
    ElMessage.error(t('appAutomation.recorder.discoverFailed'))
  }
}

const handleDeviceChange = (id) => {
  if (!id) return
  screenshot.value = ''
  captureScreen()
}

// ========== 截图 ==========
const captureScreen = async () => {
  if (!selectedDeviceId.value) return
  capturing.value = true
  try {
    const res = await captureDeviceScreenshot(selectedDeviceId.value)
    const data = res.data || res
    if (data && data.data && data.data.content) {
      screenshot.value = data.data.content
      await nextTick()
      if (imageRef.value) {
        deviceWidth.value = imageRef.value.naturalWidth || 0
        deviceHeight.value = imageRef.value.naturalHeight || 0
      }
    } else if (data && data.content) {
      screenshot.value = data.content
      await nextTick()
      if (imageRef.value) {
        deviceWidth.value = imageRef.value.naturalWidth || 0
        deviceHeight.value = imageRef.value.naturalHeight || 0
      }
    } else {
      ElMessage.warning(data.msg || t('appAutomation.recorder.captureFailed'))
    }
  } catch (e) {
    const msg = (e.response && e.response.data && e.response.data.msg) || t('appAutomation.recorder.captureFailed')
    ElMessage.error(msg)
  } finally {
    capturing.value = false
  }
}

const handleImageLoad = () => {
  if (imageWrapper.value && imageRef.value) {
    const naturalW = imageRef.value.naturalWidth
    const naturalH = imageRef.value.naturalHeight
    deviceWidth.value = naturalW || deviceWidth.value
    deviceHeight.value = naturalH || deviceHeight.value
    // 计算图片在容器内的实际显示区域（object-fit: contain 居中缩放）
    const boxW = imageWrapper.value.clientWidth
    const boxH = imageWrapper.value.clientHeight
    const ratio = Math.min(boxW / naturalW, boxH / naturalH)
    const shownW = naturalW * ratio
    const shownH = naturalH * ratio
    displayWidth.value = shownW
    displayHeight.value = shownH
    imageOffsetX.value = (boxW - shownW) / 2
    imageOffsetY.value = (boxH - shownH) / 2
  }
}

const handleAutoRefreshChange = (val) => {
  if (val) {
    startAutoRefresh()
  } else {
    stopAutoRefresh()
  }
}

const startAutoRefresh = () => {
  stopAutoRefresh()
  refreshTimer = setInterval(() => {
    if (!capturing.value) captureScreen()
  }, 3000)
}

const stopAutoRefresh = () => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

// ========== 坐标换算 ==========
const toDevicePoint = (offsetX, offsetY) => {
  const ratioX = deviceWidth.value / displayWidth.value
  const ratioY = deviceHeight.value / displayHeight.value
  return {
    x: Math.round((offsetX - imageOffsetX.value) * ratioX),
    y: Math.round((offsetY - imageOffsetY.value) * ratioY)
  }
}

const isPointInDevice = (p) => {
  return p.x >= 0 && p.y >= 0 && p.x <= deviceWidth.value && p.y <= deviceHeight.value
}

// ========== 画布交互 ==========
const handleMouseDown = (e) => {
  if (!screenshot.value) return
  mouseDown.value = true
  const rect = imageWrapper.value.getBoundingClientRect()
  dragStart.value = {
    x: e.clientX - rect.left,
    y: e.clientY - rect.top
  }
  selection.value = { ...dragStart.value, w: 0, h: 0 }
}

const handleMouseMove = (e) => {
  if (!mouseDown.value || !dragStart.value) return
  const rect = imageWrapper.value.getBoundingClientRect()
  const curX = e.clientX - rect.left
  const curY = e.clientY - rect.top
  selection.value = {
    x: Math.min(dragStart.value.x, curX),
    y: Math.min(dragStart.value.y, curY),
    w: Math.abs(curX - dragStart.value.x),
    h: Math.abs(curY - dragStart.value.y)
  }
}

const handleMouseUp = (e) => {
  if (!mouseDown.value) return
  mouseDown.value = false
  selection.value = null

  const rect = imageWrapper.value.getBoundingClientRect()
  const endX = e.clientX - rect.left
  const endY = e.clientY - rect.top

  if (!dragStart.value) return
  const start = dragStart.value
  dragStart.value = null

  const dist = Math.sqrt((endX - start.x) ** 2 + (endY - start.y) ** 2)

  if (dist < 8) {
    // 点击
    const point = toDevicePoint(endX, endY)
    handleClick(point)
  } else {
    // 滑动
    const p1 = toDevicePoint(start.x, start.y)
    const p2 = toDevicePoint(endX, endY)
    handleSwipe(p1, p2)
  }
}

// ========== 操作处理 ==========
const handleClick = async (point) => {
  if (!isPointInDevice(point)) {
    ElMessage.warning(t('appAutomation.recorder.clickOutOfScreen'))
    return
  }
  // 输入模式：先选点，等待提交文本
  if (textNeedsPoint.value && pendingText.value) {
    textPoint.value = `${point.x},${point.y}`
    return
  }

  if (activeAction.value === 'long_press') {
    if (syncToDevice.value) {
      await execDeviceAction('long_press', { ...point, duration: longPressDuration.value })
    }
    if (recording.value) {
      addStep({
        type: 'long_press',
        name: `${t('appAutomation.recorder.nameLongPress')} (${point.x}, ${point.y})`,
        config: {
          selector_type: 'pos',
          selector: `${point.x},${point.y}`,
          duration: longPressDuration.value
        }
      })
    }
    return
  }

  // 普通点击
  if (syncToDevice.value) {
    await execDeviceAction('tap', point)
  }
  if (recording.value) {
    addStep({
      type: 'click',
      name: `${t('appAutomation.recorder.nameClick')} (${point.x}, ${point.y})`,
      config: {
        selector_type: 'pos',
        selector: `${point.x},${point.y}`
      }
    })
  }
}

const handleSwipe = async (p1, p2) => {
  if (!isPointInDevice(p1) || !isPointInDevice(p2)) {
    ElMessage.warning(t('appAutomation.recorder.clickOutOfScreen'))
    return
  }
  if (syncToDevice.value) {
    await execDeviceAction('swipe', { x1: p1.x, y1: p1.y, x2: p2.x, y2: p2.y, duration: 0.5 })
  }
  if (recording.value) {
    addStep({
      type: 'swipe',
      name: `${t('appAutomation.recorder.nameSwipe')} (${p1.x},${p1.y})->(${p2.x},${p2.y})`,
      config: {
        selector_type: 'pos',
        selector: JSON.stringify([[p1.x, p1.y], [p2.x, p2.y]]),
        duration: 0.5
      }
    })
  }
}

const commitTextStep = async () => {
  if (!pendingText.value) return

  let point = null
  if (textNeedsPoint.value) {
    if (textPoint.value) {
      const [x, y] = textPoint.value.split(',').map(Number)
      point = { x, y }
    } else {
      ElMessage.info(t('appAutomation.recorder.selectPointFirst'))
      return
    }
  }

  if (syncToDevice.value) {
    if (point) {
      await execDeviceAction('tap', point)
    }
    await execDeviceAction('text', { text: pendingText.value })
  }

  if (recording.value) {
    const config = {
      selector_type: 'pos',
      selector: point ? `${point.x},${point.y}` : '0,0',
      value: pendingText.value
    }
    if (!point) {
      // 无坐标输入：仅 text，去掉 selector 相关配置
      delete config.selector_type
      delete config.selector
    }
    addStep({
      type: 'input',
      name: `${t('appAutomation.recorder.nameInput')} ${pendingText.value}`,
      config
    })
  }

  pendingText.value = ''
  textPoint.value = ''
}

// ========== 手动添加步骤 ==========
const addWaitStep = async () => {
  const { value } = await ElMessageBox.prompt(
    t('appAutomation.recorder.waitSecondsPrompt'),
    t('appAutomation.recorder.addWait'),
    {
      inputValue: '1',
      inputPattern: /^\d+(\.\d+)?$/,
      inputErrorMessage: t('appAutomation.recorder.invalidNumber')
    }
  )
  const seconds = parseFloat(value)
  if (syncToDevice.value && recording.value) {
    await execDeviceAction('sleep', { seconds })
  }
  addStep({
    type: 'wait',
    name: `${t('appAutomation.recorder.nameWait')} ${seconds}s`,
    config: { timeout: seconds }
  })
}

const KEY_EVENTS = [
  { keycode: 4, name: '返回', airtestName: 'BACK' },
  { keycode: 3, name: 'Home', airtestName: 'HOME' },
  { keycode: 82, name: '菜单', airtestName: 'MENU' },
  { keycode: 66, name: '回车', airtestName: 'ENTER' },
  { keycode: 67, name: '删除', airtestName: 'DEL' },
  { keycode: 187, name: '最近任务', airtestName: 'APP_SWITCH' }
]

const addKeyeventStep = async () => {
  const { value } = await ElMessageBox.prompt(
    t('appAutomation.recorder.keyPrompt'),
    t('appAutomation.recorder.addKey'),
    {
      inputValue: '4',
      inputPattern: /^\d+$/,
      inputErrorMessage: t('appAutomation.recorder.invalidNumber')
    }
  )
  const keycode = parseInt(value, 10)
  const keyInfo = KEY_EVENTS.find(k => k.keycode === keycode) || { keycode, name: `KEYCODE_${keycode}`, airtestName: String(keycode) }

  if (syncToDevice.value && recording.value) {
    await execDeviceAction('keyevent', { keycode })
  }
  addStep({
    type: 'keyevent',
    name: `${t('appAutomation.recorder.nameKey')} ${keyInfo.name}`,
    config: {
      keycode,
      keycode_name: keyInfo.airtestName
    }
  })
}

// ========== 步骤管理 ==========
const addStep = (step) => {
  steps.value.push(step)
  activeStepIndex.value = steps.value.length - 1
}

const removeStep = (index) => {
  steps.value.splice(index, 1)
  if (activeStepIndex.value === index) activeStepIndex.value = null
}

const moveStep = (index, dir) => {
  const target = index + dir
  if (target < 0 || target >= steps.value.length) return
  const arr = steps.value
  ;[arr[index], arr[target]] = [arr[target], arr[index]]
  activeStepIndex.value = target
}

const clearSteps = () => {
  steps.value = []
  activeStepIndex.value = null
  ElMessage.success(t('appAutomation.recorder.cleared'))
}

const stepTypeLabel = (type) => {
  const map = {
    click: t('appAutomation.recorder.typeClick'),
    input: t('appAutomation.recorder.typeInput'),
    swipe: t('appAutomation.recorder.typeSwipe'),
    long_press: t('appAutomation.recorder.typeLongPress'),
    wait: t('appAutomation.recorder.typeWait'),
    keyevent: t('appAutomation.recorder.typeKey')
  }
  return map[type] || type
}

// ========== 录制控制 ==========
const startRecording = () => {
  recording.value = true
  ElMessage.success(t('appAutomation.recorder.recordingStarted'))
}

const stopRecording = () => {
  recording.value = false
  ElMessage.success(t('appAutomation.recorder.recordingStopped', { count: steps.value.length }))
}

// ========== 设备动作 ==========
const execDeviceAction = async (action, params = {}) => {
  if (!selectedDeviceId.value) return
  try {
    await sendDeviceAction(selectedDeviceId.value, { action, params })
  } catch (e) {
    const msg = (e.response && e.response.data && e.response.data.msg) || t('appAutomation.recorder.actionFailed')
    ElMessage.warning(msg)
  }
}

// ========== 保存为测试用例 ==========
const openSaveDialog = () => {
  saveForm.value = { name: '', project: null, description: '' }
  saveDialogVisible.value = true
}

const saveAsCase = async () => {
  if (!saveForm.value.name) {
    ElMessage.warning(t('appAutomation.recorder.inputCaseName'))
    return
  }

  saving.value = true
  try {
    const uiFlow = steps.value.map(step => {
      const copy = JSON.parse(JSON.stringify(step))
      return copy
    })

    const caseData = {
      name: saveForm.value.name,
      description: saveForm.value.description,
      project: saveForm.value.project || null,
      ui_flow: uiFlow,
      variables: []
    }

    const res = await createTestCase(caseData)
    const data = res.data || res
    if (data && (data.id || data.success)) {
      ElMessage.success(t('appAutomation.recorder.saveSuccess'))
      saveDialogVisible.value = false
      // 保存成功后清空已录制的步骤，方便开始下一次录制
      clearSteps()
    } else {
      ElMessage.warning(data.msg || t('appAutomation.recorder.saveFailed'))
    }
  } catch (e) {
    const msg = (e.response && e.response.data && e.response.data.msg) || t('appAutomation.recorder.saveFailed')
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

// ========== 导出 Airtest 脚本 ==========
const openExportDialog = () => {
  exportDialogVisible.value = true
}

const escapePyString = (str) => {
  return String(str).replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n')
}

const generateAirtestScript = () => {
  const lines = [
    '# -*- encoding=utf8 -*-',
    '# 由 TestHub 脚本录制器自动生成',
    'from airtest.core.api import *',
    '',
    'auto_setup(__file__)',
    ''
  ]

  for (const step of steps.value) {
    const cfg = step.config || {}
    switch (step.type) {
      case 'click':
        lines.push(`touch((${cfg.selector}))  # ${step.name}`)
        break
      case 'input': {
        const value = escapePyString(cfg.value || '')
        if (cfg.selector && cfg.selector !== '0,0') {
          lines.push(`touch((${cfg.selector}))`)
          lines.push(`text("${value}")  # ${step.name}`)
        } else {
          lines.push(`text("${value}")  # ${step.name}`)
        }
        break
      }
      case 'swipe': {
        try {
          const arr = JSON.parse(cfg.selector)
          const s = `${arr[0][0]}, ${arr[0][1]}`
          const e = `${arr[1][0]}, ${arr[1][1]}`
          lines.push(`swipe((${s}), (${e}), duration=${cfg.duration || 0.5})  # ${step.name}`)
        } catch (err) {
          lines.push(`# 无法解析滑动坐标: ${step.name}`)
        }
        break
      }
      case 'long_press':
        lines.push(`touch((${cfg.selector}), duration=${cfg.duration || 2})  # ${step.name}`)
        break
      case 'wait':
        lines.push(`sleep(${cfg.timeout || 1})  # ${step.name}`)
        break
      case 'keyevent': {
        const keyName = cfg.keycode_name || cfg.keycode
        const airtestKey = /^\d+$/.test(String(keyName)) ? `KEYCODE_${keyName}` : keyName
        lines.push(`keyevent("${airtestKey}")  # ${step.name}`)
        break
      }
      default:
        break
    }
  }

  return lines.join('\n')
}

const downloadScript = () => {
  const name = (saveForm.value.name || 'recorded_script').replace(/[\\/:*?"<>|]/g, '_')
  const blob = new Blob([airtestScript.value], { type: 'text/x-python;charset=utf-8' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `${name}.py`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
  ElMessage.success(t('appAutomation.recorder.downloadSuccess'))
}
</script>

<style scoped>
.script-recorder {
  padding: 4px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.page-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.recorder-card {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-weight: 600;
}

.card-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.screen-area {
  position: relative;
}

.screen-wrapper {
  position: relative;
  width: 100%;
  max-height: 560px;
  height: 560px;
  cursor: crosshair;
  user-select: none;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
  background: #0f1115;
  display: flex;
  align-items: center;
  justify-content: center;
}

.screen-wrapper.recording {
  border-color: #f56c6c;
  box-shadow: 0 0 0 2px rgba(245, 108, 108, 0.15);
}

.screen-image {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
  pointer-events: none;
}

.selection-box {
  position: absolute;
  border: 1.5px dashed #409eff;
  background: rgba(64, 158, 255, 0.12);
  pointer-events: none;
  z-index: 2;
}

.recording-badge {
  position: absolute;
  top: 10px;
  left: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
  color: #fff;
  background: rgba(245, 108, 108, 0.9);
  padding: 4px 10px;
  border-radius: 12px;
  font-size: 12px;
  z-index: 3;
}

.rec-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #fff;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.screen-empty {
  min-height: 320px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #e4e7ed;
  border-radius: 4px;
}

.screen-tip {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.control-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.mode-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.mode-label {
  color: #606266;
  font-size: 13px;
  white-space: nowrap;
}

.input-panel {
  margin-bottom: 12px;
}

.input-row {
  display: flex;
  gap: 8px;
}

.input-tip {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  flex-wrap: wrap;
}

.text-point-info {
  color: #409eff;
}

.add-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.steps-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  margin-bottom: 10px;
}

.steps-header > span {
  margin-right: auto;
  font-size: 13px;
}

.steps-empty {
  padding: 10px 0;
}

.steps-list {
  max-height: 380px;
  overflow-y: auto;
  border: 1px solid #f0f2f5;
  border-radius: 6px;
  padding: 4px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 4px;
  transition: background 0.2s;
}

.step-item:hover {
  background: #f5f7fa;
}

.step-item.active {
  background: #ecf5ff;
}

.step-index {
  width: 22px;
  height: 22px;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #409eff;
  color: #fff;
  border-radius: 50%;
  font-size: 12px;
}

.step-type {
  flex-shrink: 0;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  background: #909399;
}

.step-type.type-click { background: #409eff; }
.step-type.type-input { background: #67c23a; }
.step-type.type-swipe { background: #e6a23c; }
.step-type.type-long_press { background: #f56c6c; }
.step-type.type-wait { background: #909399; }
.step-type.type-keyevent { background: #b88230; }

.step-name {
  flex: 1;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-actions {
  display: flex;
  gap: 0;
  flex-shrink: 0;
}

.export-tip {
  color: #909399;
  font-size: 12px;
  margin-bottom: 10px;
}

.export-code {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}
</style>
