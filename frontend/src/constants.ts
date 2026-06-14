const CLASS_COLORS = [
  'rgba(255, 0, 0, 0.5)',
  'rgba(0, 0, 255, 0.5)',
  'rgba(0, 255, 0, 0.5)',
  'rgba(0, 255, 255, 0.5)',
  'rgba(56, 189, 248, 0.45)',
  'rgba(255, 0, 255, 0.45)',
  'rgba(255, 128, 0, 0.45)',
  'rgba(128, 0, 255, 0.45)',
];

export function classColor(classId: number): string {
  return CLASS_COLORS[classId] ?? generatedClassColor(classId);
}

function generatedClassColor(classId: number): string {
  const red = (37 * classId + 80) % 256;
  const green = (67 * classId + 140) % 256;
  const blue = (97 * classId + 200) % 256;
  return `rgba(${red}, ${green}, ${blue}, 0.45)`;
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
