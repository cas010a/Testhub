import request from '@/utils/api'

// ========== 管理员：用户管理 ==========

// 获取用户管理列表（仅管理员）
export function getUserManageList(params) {
  return request({
    url: '/users/manage/',
    method: 'get',
    params
  })
}

// 创建用户（仅管理员）
export function createUser(data) {
  return request({
    url: '/users/manage/',
    method: 'post',
    data
  })
}

// 更新用户（资料/角色/启禁用/重置密码，仅管理员）
export function updateUser(id, data) {
  return request({
    url: `/users/manage/${id}/`,
    method: 'patch',
    data
  })
}

// 删除用户（仅管理员）
export function deleteUser(id) {
  return request({
    url: `/users/manage/${id}/`,
    method: 'delete'
  })
}
