import { FileImage, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState, type ChangeEvent, type DragEvent, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../../api/endpoints'
import { Button, Card, MedicalDisclaimer, Notice, PageHeader, SelectInput, TextArea } from '../../components/ui'
import { errorMessage } from '../../hooks/useApi'
import { useToast } from '../../hooks/useToast'
import { formatBytes } from '../../utils/format'
import { MAX_UPLOAD_MB, checkFile } from '../../utils/validation'

export function XrayUpload() {
  const navigate = useNavigate()
  const toast = useToast()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [view, setView] = useState('PA')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview) }, [preview])

  const choose = (f: File | undefined) => {
    setSubmitError(null)
    if (!f) return
    const err = checkFile(f)
    setFileError(err)
    if (err) {
      setFile(null)
      setPreview(null)
      return
    }
    setFile(f)
    setPreview(URL.createObjectURL(f))
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDragging(false)
    choose(e.dataTransfer.files?.[0])
  }

  const clear = () => {
    setFile(null)
    setPreview(null)
    setFileError(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!file) {
      setFileError('Choose an image to upload.')
      return
    }
    setBusy(true)
    setSubmitError(null)
    try {
      const x = await api.uploadXray(file, view, note)
      toast('success', 'X-ray uploaded securely.')
      navigate(`/patient/xrays/${x.id}`)
    } catch (err) {
      setSubmitError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader title="Upload a chest X-ray" subtitle="Images are stored privately and shared only with doctors assigned to you." />
      <div className="grid-2-1">
        <Card>
          <form onSubmit={submit} className="stack" noValidate>
            <div className={`dropzone ${dragging ? 'dragging' : ''} ${fileError ? 'invalid' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={onDrop}>
              {preview && file ? (
                <div className="dropzone-preview">
                  <img src={preview} alt="Selected X-ray preview" />
                  <div>
                    <p className="truncate"><strong>{file.name}</strong></p>
                    <p className="muted small">{formatBytes(file.size)}</p>
                    <Button type="button" variant="ghost" icon={<X size={16} />} onClick={clear}>Remove</Button>
                  </div>
                </div>
              ) : (
                <>
                  <FileImage size={32} aria-hidden className="muted" />
                  <p><strong>Drag an image here</strong> or</p>
                  <Button type="button" variant="secondary" onClick={() => inputRef.current?.click()}>Choose file</Button>
                  <p className="small muted">PNG or JPEG, up to {MAX_UPLOAD_MB} MB. DICOM is not supported yet.</p>
                </>
              )}
              <input ref={inputRef} type="file" accept="image/png,image/jpeg" className="sr-only" aria-label="X-ray image file"
                onChange={(e: ChangeEvent<HTMLInputElement>) => choose(e.target.files?.[0])} />
            </div>
            {fileError && <p className="field-error" role="alert">{fileError}</p>}

            <SelectInput label="Projection / view" value={view} onChange={(e) => setView(e.target.value)} hint="If you are unsure, choose “Unknown”.">
              <option value="PA">PA (posterior–anterior)</option>
              <option value="AP">AP (anterior–posterior)</option>
              <option value="lateral">Lateral</option>
              <option value="unknown">Unknown</option>
            </SelectInput>
            <TextArea label="Note for your doctor (optional)" maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
              hint="For example, when the X-ray was taken and why. Do not include other people's information." />
            {submitError && <p className="form-error" role="alert">{submitError}</p>}
            <div><Button type="submit" loading={busy} icon={<Upload size={16} />} disabled={!file}>Upload securely</Button></div>
          </form>
        </Card>
        <div className="stack">
          <Notice title="Before you upload">
            <ul className="bullets">
              <li>Upload a frontal chest X-ray exported as an image file.</li>
              <li>Crop out or avoid images that show names or ID numbers.</li>
              <li>Embedded photo metadata (EXIF) is removed automatically.</li>
            </ul>
          </Notice>
          <MedicalDisclaimer compact />
        </div>
      </div>
    </>
  )
}
