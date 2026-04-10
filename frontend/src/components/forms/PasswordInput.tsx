import clsx from 'clsx'
import { Eye, EyeOff } from 'lucide-react'
import { useId, useState } from 'react'

type PasswordInputProps = {
  value: string
  onChange: (value: string) => void
  className?: string
  placeholder?: string
  autoComplete?: string
  disabled?: boolean
}

export function PasswordInput({
  value,
  onChange,
  className,
  placeholder,
  autoComplete,
  disabled = false,
}: PasswordInputProps) {
  const [visible, setVisible] = useState(false)
  const visibilityLabelId = useId()

  return (
    <div className="relative">
      <input
        type={visible ? 'text' : 'password'}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={clsx(className, 'pr-12')}
        placeholder={placeholder}
        autoComplete={autoComplete}
        disabled={disabled}
        aria-describedby={visibilityLabelId}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        className="absolute inset-y-0 right-0 inline-flex w-12 items-center justify-center text-slate-400 transition hover:text-white"
        aria-label={visible ? 'Скрыть значение' : 'Показать значение'}
      >
        {visible ? <EyeOff size={18} /> : <Eye size={18} />}
      </button>
      <span id={visibilityLabelId} className="sr-only">
        {visible ? 'Значение отображается открыто' : 'Значение скрыто'}
      </span>
    </div>
  )
}
