import { describe, expect, it } from 'vitest'
import { backendWeekday, startTimesWithin } from '../utils/format'
import { checkFile, validateRegistration, validateSlots, type RegisterForm } from '../utils/validation'

const valid: RegisterForm = {
  full_name: 'Asha Patient', email: 'asha@example.com', password: 'Secret12345', confirm: 'Secret12345',
  date_of_birth: '', sex: '', phone: '',
}

describe('registration validation', () => {
  it('accepts a valid form', () => {
    expect(validateRegistration(valid)).toEqual({})
  })
  it('flags each invalid field', () => {
    const errors = validateRegistration({ ...valid, full_name: 'A', email: 'nope', password: 'short', confirm: 'x', date_of_birth: '2999-01-01' })
    expect(Object.keys(errors).sort()).toEqual(['confirm', 'date_of_birth', 'email', 'full_name', 'password'])
  })
  it('rejects letters-only passwords', () => {
    expect(validateRegistration({ ...valid, password: 'abcdefghijk', confirm: 'abcdefghijk' }).password).toMatch(/Mix/)
  })
})

describe('upload pre-check', () => {
  const file = (name: string, type: string, size: number) => new File([new Uint8Array(size)], name, { type })
  it('accepts PNG and JPEG', () => {
    expect(checkFile(file('a.png', 'image/png', 100))).toBeNull()
    expect(checkFile(file('a.jpg', 'image/jpeg', 100))).toBeNull()
  })
  it('rejects other types, empty and oversized files', () => {
    expect(checkFile(file('a.pdf', 'application/pdf', 100))).toMatch(/PNG or JPEG/)
    expect(checkFile(file('a.png', 'image/png', 0))).toMatch(/empty/)
    expect(checkFile(file('a.png', 'image/png', 11 * 1024 * 1024))).toMatch(/too large/)
  })
})

describe('availability helpers', () => {
  it('detects overlapping and inverted slots', () => {
    expect(validateSlots([{ weekday: 0, start_time: '09:00', end_time: '12:00' }])).toBeNull()
    expect(validateSlots([{ weekday: 0, start_time: '12:00', end_time: '09:00' }])).toMatch(/before/)
    expect(validateSlots([
      { weekday: 1, start_time: '09:00', end_time: '12:00' },
      { weekday: 1, start_time: '11:00', end_time: '13:00' },
    ])).toMatch(/overlap/)
  })
  it('generates start times that fit the duration', () => {
    expect(startTimesWithin([{ start_time: '09:00:00', end_time: '10:00:00' }], 30)).toEqual(['09:00', '09:15', '09:30'])
  })
  it('maps dates to backend weekdays (Monday = 0)', () => {
    expect(backendWeekday('2026-11-02')).toBe(0) // a Monday
    expect(backendWeekday('2026-11-08')).toBe(6) // a Sunday
  })
})
