// Formats integer cents as currency. Pure / props-only.

import { formatMoney } from "../../lib/format.js";

export default function Money({ cents, className }) {
  return <span className={className}>{formatMoney(cents)}</span>;
}
