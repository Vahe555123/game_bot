import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

type FieldMeta = {
  label: string
  hint?: string
  error?: string | null
}

type FieldWrapperProps = FieldMeta & {
  children: ReactNode
}

type TextFieldProps = FieldMeta & InputHTMLAttributes<HTMLInputElement>
type SelectFieldProps = FieldMeta &
  SelectHTMLAttributes<HTMLSelectElement> & { options: Array<{ value: string; label: string }> }

function FieldWrapper({ label, hint, error, children }: FieldWrapperProps) {
  return (
    <label className="block space-y-2">
      <span className="flex items-center justify-between gap-3 text-sm font-semibold text-slate-100">
        <span>{label}</span>
        {hint ? <span className="text-xs font-medium text-slate-400">{hint}</span> : null}
      </span>
      {children}
      {error ? <p className="text-sm text-rose-300">{error}</p> : null}
    </label>
  )
}

export function TextField({ label, hint, error, className = '', ...props }: TextFieldProps) {
  return (
    <FieldWrapper label={label} hint={hint} error={error}>
      <input {...props} className={`auth-input ${className}`.trim()} />
    </FieldWrapper>
  )
}

export function SelectField({
  label,
  hint,
  error,
  options,
  className = '',
  ...props
}: SelectFieldProps) {
  return (
    <FieldWrapper label={label} hint={hint} error={error}>
      <select {...props} className={`auth-input ${className}`.trim()}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </FieldWrapper>
  )
}
