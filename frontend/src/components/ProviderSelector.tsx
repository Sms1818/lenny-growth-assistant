import type { ProviderMode } from "../types/api";

const MODES: { value: ProviderMode; label: string; hint: string }[] = [
  {
    value: "auto",
    label: "Auto",
    hint: "Local first with optional cloud fallback for artifacts",
  },
  {
    value: "local",
    label: "Local",
    hint: "Force Ollama local models",
  },
  {
    value: "cloud",
    label: "Cloud",
    hint: "Force configured cloud provider",
  },
];

interface ProviderSelectorProps {
  value: ProviderMode;
  onChange: (mode: ProviderMode) => void;
  disabled?: boolean;
}

export function ProviderSelector({
  value,
  onChange,
  disabled = false,
}: ProviderSelectorProps) {
  return (
    <div className="provider-selector" role="group" aria-label="Provider mode">
      <span className="provider-selector__label">Provider</span>
      <div className="provider-selector__options">
        {MODES.map((mode) => (
          <button
            key={mode.value}
            type="button"
            className={`provider-selector__option ${value === mode.value ? "provider-selector__option--active" : ""}`}
            onClick={() => onChange(mode.value)}
            disabled={disabled}
            aria-pressed={value === mode.value}
            title={mode.hint}
          >
            {mode.label}
          </button>
        ))}
      </div>
    </div>
  );
}
