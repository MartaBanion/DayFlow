import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, taskApi } from './api'
import { createTaskWithConflict, updateTaskWithConflict } from './taskSave'
import type { Task } from './types'

const task: Task = {
  id: 'task-1',
  title: '时间块任务',
  description: null,
  status: 'pending',
  planned_date: '2026-09-26',
  start_at_utc: null,
  end_at_utc: null,
  schedule_timezone: null,
  priority: 'normal',
  category: null,
  tags: [],
  created_at_utc: '2026-09-26T00:00:00.000Z',
  updated_at_utc: '2026-09-26T00:00:00.000Z',
  completed_at_utc: null,
  deleted_at_utc: null,
  version: 2,
}

const payload = {
  planned_date: '2026-09-26',
  schedule: { start_time: '14:00', end_time: '15:00', timezone: 'Asia/Shanghai' },
}

afterEach(() => vi.restoreAllMocks())

describe('schedule conflict save flow', () => {
  it('does not retry when the user cancels the conflict confirmation', async () => {
    const update = vi
      .spyOn(taskApi, 'update')
      .mockRejectedValue(new ApiRequestError('overlap', 409, 'schedule_conflict'))

    const result = await updateTaskWithConflict(task, payload, async () => false)

    expect(result).toBeNull()
    expect(update).toHaveBeenCalledTimes(1)
  })

  it('retries the same update with an explicit conflict override', async () => {
    const saved = { ...task, version: 3 }
    const update = vi
      .spyOn(taskApi, 'update')
      .mockRejectedValueOnce(new ApiRequestError('overlap', 409, 'schedule_conflict'))
      .mockResolvedValueOnce(saved)

    const result = await updateTaskWithConflict(task, payload, async () => true)

    expect(result).toEqual(saved)
    expect(update).toHaveBeenNthCalledWith(2, task.id, task.version, payload, {
      allowScheduleConflict: true,
    })
  })

  it('propagates a stale-version error from the override attempt', async () => {
    const stale = new ApiRequestError('stale', 409, 'task_version_conflict')
    vi.spyOn(taskApi, 'update')
      .mockRejectedValueOnce(new ApiRequestError('overlap', 409, 'schedule_conflict'))
      .mockRejectedValueOnce(stale)

    await expect(updateTaskWithConflict(task, payload, async () => true)).rejects.toBe(stale)
  })

  it('applies the same confirm-and-override flow to task creation', async () => {
    const created = { ...task, id: 'created-task' }
    const create = vi
      .spyOn(taskApi, 'create')
      .mockRejectedValueOnce(new ApiRequestError('overlap', 409, 'schedule_conflict'))
      .mockResolvedValueOnce(created)

    const result = await createTaskWithConflict(
      { title: task.title, description: null, planned_date: task.planned_date, schedule: payload.schedule },
      async () => true,
    )

    expect(result).toEqual(created)
    expect(create).toHaveBeenNthCalledWith(2, expect.anything(), {
      allowScheduleConflict: true,
    })
  })
})
