// 解析 AI 生成的测试用例文本（final_test_cases，Markdown 表格或结构化文本）
// 返回: [{ caseId, scenario, precondition, steps, expected, priority }]
export function parseTestCases(content) {
  if (!content) return []

  // 去除markdown加粗标记，保留纯净文本
  let cleanContent = content.replace(/\*\*([^*]+)\*\*/g, '$1')

  const lines = cleanContent.split('\n').filter(line => line.trim())
  const testCases = []

  // 尝试解析表格格式
  let isTableFormat = false
  const tableData = []

  for (let line of lines) {
    const trimmedLine = line.trim()
    if (trimmedLine.includes('|') && !trimmedLine.includes('--------')) {
      // 跳过 markdown 表头分隔行（如 | --- | --- | 或 | :---: | --- |）
      const sepCells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell)
      const isSeparator = sepCells.length > 0 && sepCells.every(cell => /^:?-+:?$/.test(cell))
      if (isSeparator) continue
      const cells = trimmedLine.split('|').map(cell => cell.trim()).filter(cell => cell)
      if (cells.length > 1) {
        tableData.push(cells)
        isTableFormat = true
      }
    }
  }

  if (isTableFormat && tableData.length > 1) {
    // 表格格式解析
    const headers = tableData[0]
    for (let i = 1; i < tableData.length; i++) {
      const row = tableData[i]
      const testCase = {}

      // 清理<br>标签的辅助函数
      const cleanBrTags = (text) => {
        if (!text) return ''
        return text.replace(/<br\s*\/?>/gi, '\n')
      }

      headers.forEach((header, index) => {
        const value = cleanBrTags(row[index] || '')

        // 使用更精确的匹配逻辑，避免误判
        const cleanHeader = header.trim().toLowerCase()

        // 优先级匹配，避免误判
        if (cleanHeader === '优先级' || cleanHeader === 'priority' || cleanHeader === 'priority（优先级）' || cleanHeader === '优先级（priority）') {
          testCase.priority = value
        } else if (cleanHeader === '用例id' || cleanHeader === '编号' || cleanHeader === 'id' || cleanHeader.includes('用例id')) {
          testCase.caseId = value
        } else if (cleanHeader === '测试目标' || cleanHeader === '测试场景' || cleanHeader === '场景' || cleanHeader === '标题' || cleanHeader.includes('测试目标')) {
          testCase.scenario = value
        } else if (cleanHeader === '前置条件' || cleanHeader === '前置' || cleanHeader === '前提条件') {
          testCase.precondition = value
        } else if (cleanHeader === '测试步骤' || cleanHeader === '操作步骤' || cleanHeader === '步骤') {
          // 确保不要误匹配"预期结果"中包含的"步骤"字样
          if (!cleanHeader.includes('预期') && !cleanHeader.includes('结果')) {
            testCase.steps = value
          }
        } else if (cleanHeader === '预期结果' || cleanHeader === '预期' || cleanHeader === '结果' || cleanHeader.includes('预期结果')) {
          testCase.expected = value
        }
      })

      if (testCase.scenario || testCase.caseId) {
        // If steps field is empty, use scenario as default
        if (!testCase.steps && testCase.scenario) {
          testCase.steps = testCase.scenario
        }
        // 如果没有priority，设置默认值
        if (!testCase.priority) {
          testCase.priority = 'P2'
        }
        testCases.push(testCase)
      }
    }
  } else {
    // 结构化文本格式解析
    let currentTestCase = {}
    let caseNumber = 1

    for (const line of lines) {
      if (line.includes('测试用例') || line.includes('Test Case') ||
          line.match(/^(\d+\.|\*|\-|\d+、)/)) {

        if (Object.keys(currentTestCase).length > 0) {
          testCases.push(currentTestCase)
          caseNumber++
        }

        currentTestCase = {
          caseId: `TC${String(caseNumber).padStart(3, '0')}`,
          scenario: line.replace(/^(\d+\.|\*|\-|\d+、)\s*/, '').replace(/测试用例\d*[:：]?\s*/, '').replace(/Test Case\s*\d*[:：]?\s*/i, ''),
          precondition: '',
          steps: '',
          expected: '',
          priority: 'P2'
        }
      } else if (line.includes('前置条件') || line.includes('前提')) {
        currentTestCase.precondition = line.replace(/.*?[:：]\s*/, '')
      } else if (line.includes('测试步骤') || line.includes('操作步骤') || line.includes('步骤')) {
        currentTestCase.steps = line.replace(/.*?[:：]\s*/, '')
      } else if (line.includes('预期结果') || line.includes('Expected')) {
        currentTestCase.expected = line.replace(/.*?[:：]\s*/, '')
      } else if (line.includes('优先级')) {
        currentTestCase.priority = line.replace(/.*?[:：]\s*/, '')
      }
    }

    if (Object.keys(currentTestCase).length > 0) {
      testCases.push(currentTestCase)
    }
  }

  return testCases
}
