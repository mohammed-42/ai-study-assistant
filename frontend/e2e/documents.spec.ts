import { test, expect } from './support/fixtures'
import { login, saveScreenshot } from './support/helpers'

const MINIMAL_PDF = Buffer.from(
  '%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n'
)

test('upload dialog requires a subject and rejects wrong file types', async ({
  page,
  e2eUser,
}) => {
  await login(page, e2eUser)
  await page.goto('/documents')
  await expect(page.getByRole('heading', { name: 'Documents', level: 1 })).toBeVisible()
  await saveScreenshot(page, 'documents')

  await page.getByRole('button', { name: 'Upload', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Upload document')).toBeVisible()

  const submit = dialog.getByRole('button', { name: 'Upload', exact: true })
  await expect(submit).toBeDisabled()

  const fileInput = dialog.locator('#upload-files')
  await fileInput.setInputFiles({
    name: 'sample.pdf',
    mimeType: 'application/pdf',
    buffer: MINIMAL_PDF,
  })
  await expect(submit).toBeDisabled()

  await fileInput.setInputFiles({
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('not a supported document'),
  })
  await expect(dialog.getByRole('alert')).toContainText(
    'notes.txt is not supported. Use PDF, JPG, PNG, or WebP.'
  )
  await saveScreenshot(page, 'upload-dialog')

  await dialog.getByRole('button', { name: 'Cancel', exact: true }).click()
  await expect(dialog).toBeHidden()
})
