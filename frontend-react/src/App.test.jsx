import React from 'react'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { vi, test, expect, beforeEach } from 'vitest'
import App from './App.jsx'

beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })
const jres = (obj) => Promise.resolve({ ok: true, headers: { get: () => 'application/json' }, json: () => Promise.resolve(obj) })

test('shows login and an error message on bad credentials', async () => {
  global.fetch = vi.fn(() => jres({ status: 'error', code: 'bad_credentials', message: 'Wrong email or password.' }))
  render(<App />)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'x' } })
  fireEvent.click(screen.getByText('Sign in', { selector: 'button' }))
  await waitFor(() => expect(screen.getByText('Wrong email or password.')).toBeTruthy())
})

test('login success shows the tabs; models tab lists models from the API', async () => {
  global.fetch = vi.fn(url => String(url).includes('/auth/login')
    ? jres({ status: 'ok', token: 't', role: 'admin', email: 'a@b.c' })
    : jres({ status: 'ok', models: [{ name: 'model_v2_svm_rbf', algo: 'svm_rbf', metrics: { test: { svm_rbf: { accuracy: 0.9, recall: 0.9, fpr: 0.04, precision: 0.99, f1: 0.95 } } } }] }))
  render(<App />)
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'a@b.c' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'pw' } })
  fireEvent.click(screen.getByText('Sign in', { selector: 'button' }))
  await waitFor(() => screen.getByText('Stego Studio'))
  fireEvent.click(screen.getByText('Models'))
  await waitFor(() => expect(screen.getByText('model_v2_svm_rbf')).toBeTruthy())
  expect(screen.getByText('0.040')).toBeTruthy()
})
