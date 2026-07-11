const CLASS_ACCENT_COLORS: Record<number, { border: string; text: string; bg: string }> = {
  0: { border: '#10b981', text: '#10b981', bg: 'rgba(6, 78, 59, 0.45)' },
  1: { border: '#eab308', text: '#eab308', bg: 'rgba(113, 63, 18, 0.45)' },
  2: { border: '#3b82f6', text: '#3b82f6', bg: 'rgba(30, 58, 138, 0.45)' },
  3: { border: '#ef4444', text: '#ef4444', bg: 'rgba(127, 29, 29, 0.45)' },
  4: { border: '#a855f7', text: '#a855f7', bg: 'rgba(88, 28, 135, 0.45)' },
  5: { border: '#f97316', text: '#f97316', bg: 'rgba(124, 45, 18, 0.45)' },
  6: { border: '#06b6d4', text: '#06b6d4', bg: 'rgba(22, 78, 99, 0.45)' },
  7: { border: '#ec4899', text: '#ec4899', bg: 'rgba(131, 24, 67, 0.45)' },
};

export function getClassAccent(classId: number) {
  return CLASS_ACCENT_COLORS[classId] ?? CLASS_ACCENT_COLORS[classId % 8];
}

export function classColor(classId: number): string {
  return getClassAccent(classId).bg;
}

export function classBorderColor(classId: number): string {
  return getClassAccent(classId).border;
}

export const DEFAULT_TASK_ID = 'safety_signs';

export const FALLBACK_CLASS_NAMES: Record<string, Record<number, string>> = {
  ppe: {
    0: 'Person',
    1: 'Helmet',
    2: 'Vest',
    3: 'Cleaning Coverall',
  },
  safety_signs: {
    0: 'M014 Wear head protection',
    1: 'M015 Wear high-visibility clothing',
    2: 'P004 No thoroughfare',
    3: 'W011 Slippery surface',
  },
};
