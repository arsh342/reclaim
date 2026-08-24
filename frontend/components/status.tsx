type Tone = "default" | "accent" | "danger" | "pending";

const TONE_STYLES: Record<Tone, string> = {
  default: "border-rule text-ink",
  accent: "border-accent text-accent",
  danger: "border-danger text-danger",
  pending: "border-pending text-pending",
};

export function Status({ value, tone = "default" }: { value: string; tone?: Tone }) {
  return (
    <span
      className={`num inline-flex items-center border px-2 py-0.5 text-xs uppercase tracking-wider ${TONE_STYLES[tone]}`}
    >
      {value}
    </span>
  );
}
