/** React Bits "Shiny Text" (https://reactbits.dev/text-animations/shiny-text) - a CSS-only
 * gradient sweep across the text, no external dependency. */

import styles from './ShinyText.module.css';

interface ShinyTextProps {
  text: string;
  className?: string;
  speed?: number;
  disabled?: boolean;
}

export function ShinyText({ text, className = '', speed = 3, disabled = false }: ShinyTextProps) {
  return (
    <span
      className={`${styles.shinyText} ${disabled ? styles.disabled : ''} ${className}`}
      style={{ animationDuration: `${speed}s` }}
    >
      {text}
    </span>
  );
}
