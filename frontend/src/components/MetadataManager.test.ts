// @vitest-environment jsdom

import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { ElMessageBox } from 'element-plus'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiRequestError, taskApi } from '../api'
import MetadataManager from './MetadataManager.vue'

const stubs = {
  'el-alert': {
    props: ['title'],
    template: '<div class="stub-alert">{{ title }}</div>',
  },
  'el-button': {
    props: ['disabled', 'loading', 'nativeType'],
    template: '<button :disabled="disabled" :type="nativeType || \'button\'" @click="$emit(\'click\')"><slot /></button>',
  },
  'el-dialog': {
    props: ['modelValue'],
    template: '<div v-if="modelValue" class="stub-dialog"><slot /></div>',
  },
  'el-divider': { template: '<hr />' },
  'el-input': {
    props: ['modelValue'],
    template: '<input v-bind="$attrs" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-tag': { template: '<span><slot /></span>' },
}

describe('MetadataManager', () => {
  let categories: { id: string; name: string }[]
  let tags: { id: string; name: string }[]
  let wrapper: VueWrapper | undefined

  beforeEach(() => {
    categories = [{ id: 'category-1', name: 'Learning' }]
    tags = [{ id: 'tag-1', name: 'linux' }]
    vi.spyOn(taskApi, 'listCategories').mockImplementation(async () => categories)
    vi.spyOn(taskApi, 'listTags').mockImplementation(async () => tags)
    vi.spyOn(taskApi, 'createCategory').mockImplementation(async (name) => {
      const category = { id: `category-${categories.length + 1}`, name }
      categories = [...categories, category]
      return category
    })
    vi.spyOn(taskApi, 'updateCategory').mockImplementation(async (id, name) => {
      categories = categories.map((category) =>
        category.id === id ? { ...category, name } : category,
      )
      return categories.find((category) => category.id === id)!
    })
    vi.spyOn(taskApi, 'removeCategory').mockImplementation(async (id) => {
      categories = categories.filter((category) => category.id !== id)
    })
    vi.spyOn(taskApi, 'createTag').mockImplementation(async (name) => {
      const tag = { id: `tag-${tags.length + 1}`, name }
      tags = [...tags, tag]
      return tag
    })
    vi.spyOn(taskApi, 'updateTag').mockImplementation(async (id, name) => {
      tags = tags.map((tag) => (tag.id === id ? { ...tag, name } : tag))
      return tags.find((tag) => tag.id === id)!
    })
    vi.spyOn(taskApi, 'removeTag').mockImplementation(async (id) => {
      tags = tags.filter((tag) => tag.id !== id)
    })
    vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue({ action: 'confirm' })
  })

  afterEach(() => {
    wrapper?.unmount()
    vi.restoreAllMocks()
  })

  async function openManager(): Promise<void> {
    wrapper = mount(MetadataManager, {
      props: { categories: [], tags: [] },
      global: { stubs },
    })
    await wrapper.get('button').trigger('click')
    await flushPromises()
  }

  it('creates, renames, and deletes categories and tags', async () => {
    await openManager()

    await wrapper!.get('input[aria-label="New category name"]').setValue('Work')
    await wrapper!.findAll('form')[0].trigger('submit')
    await flushPromises()
    expect(taskApi.createCategory).toHaveBeenCalledWith('Work')
    expect(wrapper!.text()).toContain('Work')

    const categoryRow = wrapper!.findAll('.metadata-row').find((row) => row.text().includes('Learning'))
    const categoryRename = categoryRow!.findAll('button').find((button) => button.text() === 'Rename')
    await categoryRename!.trigger('click')
    await wrapper!.get('input[aria-label="Rename category Learning"]').setValue('Study')
    await wrapper!.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(taskApi.updateCategory).toHaveBeenCalledWith('category-1', 'Study')
    expect(wrapper!.text()).toContain('Study')

    const renamedCategoryRow = wrapper!.findAll('.metadata-row').find((row) => row.text().includes('Study'))
    await renamedCategoryRow!.findAll('button').find((button) => button.text() === 'Delete')!.trigger('click')
    await flushPromises()
    expect(taskApi.removeCategory).toHaveBeenCalledWith('category-1')
    expect(wrapper!.text()).not.toContain('Study')

    await wrapper!.get('input[aria-label="New tag name"]').setValue('study')
    await wrapper!.findAll('form')[1].trigger('submit')
    await flushPromises()
    expect(taskApi.createTag).toHaveBeenCalledWith('study')
    expect(wrapper!.text()).toContain('study')

    const tagRow = wrapper!.findAll('.metadata-row').find((row) => row.text().includes('linux'))
    const tagRename = tagRow!.findAll('button').find((button) => button.text() === 'Rename')
    await tagRename!.trigger('click')
    await wrapper!.get('input[aria-label="Rename tag linux"]').setValue('systems')
    await wrapper!.findAll('button').find((button) => button.text() === 'Save')!.trigger('click')
    await flushPromises()
    expect(taskApi.updateTag).toHaveBeenCalledWith('tag-1', 'systems')
    expect(wrapper!.text()).toContain('systems')

    const renamedTagRow = wrapper!.findAll('.metadata-row').find((row) => row.text().includes('systems'))
    await renamedTagRow!.findAll('button').find((button) => button.text() === 'Delete')!.trigger('click')
    await flushPromises()
    expect(taskApi.removeTag).toHaveBeenCalledWith('tag-1')
    expect(wrapper!.text()).not.toContain('systems')
  })

  it('shows a clear duplicate error instead of a success state', async () => {
    vi.mocked(taskApi.createCategory).mockRejectedValueOnce(
      new ApiRequestError('Duplicate category', 409, 'category_name_conflict'),
    )
    await openManager()

    await wrapper!.get('input[aria-label="New category name"]').setValue('learning')
    await wrapper!.findAll('form')[0].trigger('submit')
    await flushPromises()

    expect(wrapper!.find('.stub-alert').text()).toContain(
      'A category with that name already exists.',
    )
    expect(wrapper!.text()).not.toContain('Category created')
  })
})
