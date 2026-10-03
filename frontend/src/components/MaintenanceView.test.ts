// @vitest-environment jsdom
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MaintenanceView from './MaintenanceView.vue'
import { ApiRequestError, backupApi, taskApi } from '../api'
import type { Backup, BackupVerification } from '../types'

const backup: Backup = {
  backup_version: 1, backup_id: '4bfb2916-b743-4d38-b606-93c24da78200',
  filename: 'dayflow-backup-20261001T120000000000Z-12345678901234567890123456789012.sqlite3',
  created_at_utc: '2026-10-01T12:00:00Z', app_version: '0.6.0',
  alembic_version: '0005_add_deadlines_recurrence_reminders',
  database_sha256: 'a'.repeat(64), file_size: 409600, integrity_check: 'ok',
  foreign_key_errors: 0, verified_at_utc: '2026-10-01T12:00:01Z',
  source_database: 'dayflow.sqlite3', compatible_for_restore: true,
}
const verified: BackupVerification = {
  backup_id: backup.backup_id, verified_at_utc: '2026-10-01T12:10:00Z', status: 'valid',
  compatible_for_restore: true, database_sha256: backup.database_sha256, file_size: backup.file_size,
  alembic_version: backup.alembic_version, integrity_check: 'ok', foreign_key_errors: 0,
  structure_valid: true, issues: [],
}
let wrapper: VueWrapper
function button(name: string) { return wrapper.findAll('button').find(b => b.text() === name)! }
async function open() { wrapper = mount(MaintenanceView, { global: { plugins: [ElementPlus] } }); await flushPromises() }
beforeEach(() => {
  vi.spyOn(backupApi, 'list').mockResolvedValue([])
  vi.spyOn(backupApi, 'create').mockResolvedValue(backup)
  vi.spyOn(backupApi, 'verify').mockResolvedValue(verified)
  vi.spyOn(taskApi, 'getRuntime').mockResolvedValue({ timezone: 'Asia/Shanghai', local_date: '2026-10-01', app_version: '0.6.0', database_schema: backup.alembic_version })
})
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })

describe('Maintenance UI', () => {
  it('distinguishes loading from empty and does not invent counts', async () => {
    vi.mocked(backupApi.list).mockReturnValue(new Promise(() => {}))
    await open()
    expect(wrapper.text()).toContain('正在加载备份列表…')
    expect(wrapper.text()).not.toContain('还没有备份')
    expect(wrapper.text()).not.toContain('0 份')
  })
  it('shows actual runtime status, empty action and truthful restore guidance', async () => {
    await open()
    expect(wrapper.text()).toContain('0.6.0')
    expect(wrapper.text()).toContain(backup.alembic_version)
    expect(wrapper.text()).toContain('还没有备份')
    expect(button('创建第一份备份')).toBeDefined()
    expect(wrapper.text()).toContain('当前版本仅支持创建和验证备份')
    expect(wrapper.text()).not.toContain('dayflow restore')
    expect(button('立即恢复')).toBeUndefined()
  })
  it('renders metadata in backend order, full filename and accessible SHA expansion', async () => {
    vi.mocked(backupApi.list).mockResolvedValue([backup, { ...backup, backup_id: 'second', filename: 'second.sqlite3' }])
    await open()
    expect(wrapper.findAll('article').map(a => a.attributes('aria-label'))).toEqual([`备份 ${backup.filename}`, '备份 second.sqlite3'])
    expect(wrapper.get('summary').text()).toContain('查看完整值')
    expect(wrapper.get('code').text()).toBe(backup.database_sha256)
    expect(wrapper.text()).toContain('登记验证时间')
    expect(wrapper.text()).toContain('需要验证')
    expect(wrapper.text()).not.toContain('可用于当前版本恢复')
  })
  it('creates, announces success and refreshes list without double submission', async () => {
    let resolve!: (value: Backup) => void
    vi.mocked(backupApi.create).mockReturnValue(new Promise(done => { resolve = done }))
    await open()
    await button('创建备份').trigger('click')
    await button('创建第一份备份').trigger('click')
    expect(backupApi.create).toHaveBeenCalledTimes(1)
    vi.mocked(backupApi.list).mockResolvedValue([backup])
    resolve(backup); await flushPromises()
    expect(wrapper.text()).toContain('备份已创建')
    expect(backupApi.list).toHaveBeenCalledTimes(2)
    expect(wrapper.findAll('article')).toHaveLength(1)
  })
  it('shows create failure without exposing server path or pretending success', async () => {
    vi.mocked(backupApi.create).mockRejectedValue(new ApiRequestError('/private/secret.sqlite3', 500, 'backup_registration_failed'))
    await open(); await button('创建备份').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('登记失败')
    expect(wrapper.text()).not.toContain('/private/')
    expect(wrapper.text()).not.toContain('备份已创建')
  })
  it('keeps list on verify request failure and supports retry', async () => {
    vi.mocked(backupApi.list).mockResolvedValue([backup])
    vi.mocked(backupApi.verify).mockRejectedValueOnce(new ApiRequestError('not found', 404, 'backup_not_found'))
    await open(); await button('验证').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('验证请求失败')
    expect(wrapper.findAll('article')).toHaveLength(1)
    await button('验证').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('可用于当前版本恢复')
    expect(wrapper.text()).toContain('本次验证时间')
  })
  it.each([
    ['incompatible', '不兼容 · 不可恢复'],
    ['manifest_mismatch', '元数据不匹配 · 不可恢复'],
    ['corrupted', '验证失败 · 备份损坏或结构异常'],
    ['unreadable', '验证失败 · 文件缺失、不可读或不安全'],
  ] as const)('explains %s rather than showing recoverable', async (status, text) => {
    vi.mocked(backupApi.list).mockResolvedValue([backup])
    vi.mocked(backupApi.verify).mockResolvedValue({ ...verified, status, compatible_for_restore: false, integrity_check: null, file_size: null, database_sha256: null })
    await open(); await button('验证').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain(text)
    expect(wrapper.text()).not.toContain('可用于当前版本恢复')
    expect(wrapper.text()).toContain('无法读取')
    expect(backupApi.create).not.toHaveBeenCalled()
  })
  it('does not lock unrelated backup operations during verification', async () => {
    vi.mocked(backupApi.list).mockResolvedValue([backup, { ...backup, backup_id: 'second' }])
    vi.mocked(backupApi.verify).mockReturnValue(new Promise(() => {}))
    await open(); await button('验证').trigger('click')
    expect(wrapper.findAll('article')[1]!.get('button').attributes('disabled')).toBeUndefined()
    expect(button('创建备份').attributes('disabled')).toBeUndefined()
  })
  it('shows list error and retry instead of empty, then supports refresh', async () => {
    vi.mocked(backupApi.list).mockRejectedValueOnce(new TypeError('offline'))
    await open()
    expect(wrapper.text()).toContain('备份列表加载失败')
    expect(wrapper.text()).not.toContain('还没有备份')
    await button('重试备份列表').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('还没有备份')
    await button('刷新备份列表').trigger('click'); await flushPromises()
    expect(backupApi.list).toHaveBeenCalledTimes(3)
  })
  it('reports unavailable runtime instead of deriving Schema from an old backup', async () => {
    vi.mocked(taskApi.getRuntime).mockRejectedValue(new TypeError('offline'))
    vi.mocked(backupApi.list).mockResolvedValue([backup])
    await open()
    expect(wrapper.text()).toContain('数据库状态读取失败')
    expect(wrapper.text()).toContain('未获取')
  })
  it('marks incompatible historical metadata without offering a restore command', async () => {
    vi.mocked(backupApi.list).mockResolvedValue([{ ...backup, compatible_for_restore: false, alembic_version: '0004_add_projects' }])
    await open()
    expect(wrapper.text()).toContain('不兼容 · 不可恢复')
    expect(wrapper.text()).not.toContain('dayflow restore')
  })
  it('copies full SHA or offers a manual fallback', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
    vi.mocked(backupApi.list).mockResolvedValue([backup])
    await open(); await button('复制完整 SHA').trigger('click'); await flushPromises()
    expect(writeText).toHaveBeenCalledWith(backup.database_sha256)
    expect(wrapper.text()).toContain('完整 SHA-256 已复制')
    writeText.mockRejectedValue(new Error('denied'))
    await button('复制完整 SHA').trigger('click'); await flushPromises()
    expect(wrapper.text()).toContain('手动选择完整 SHA-256')
  })
})
