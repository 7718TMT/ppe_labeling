export const CLASS_COLORS = [
  'rgba(255, 0, 0, 0.5)',
  'rgba(0, 0, 255, 0.5)',
  'rgba(0, 255, 0, 0.5)',
  'rgba(0, 255, 255, 0.5)',
  'rgba(56, 189, 248, 0.45)',
];

export const DEFAULT_TASK_ID = 'safety_signs';

export const FALLBACK_CLASS_NAMES: Record<string, Record<number, string>> = {
  ppe: {
    0: 'Person',
    1: 'Helmet',
    2: 'Vest',
  },
  safety_signs: {
    0: 'M014 Wear head protection',
    1: 'M015 Wear high-visibility clothing',
    2: 'P004 No thoroughfare',
    3: 'W011 Slippery surface',
    4: 'Unreviewed safety sign',
  },
};
