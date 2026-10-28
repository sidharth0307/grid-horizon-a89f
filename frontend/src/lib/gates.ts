export interface Gate {
  value: string;
  label: string;
  /** Pre-2021 timing kept only for comparison. */
  legacy?: boolean;
  description: string;
}

export const GATES: Gate[] = [
  {
    value: '09:20',
    label: '09:20 UK · EPEX day-ahead',
    description: 'GB day-ahead gate closure on EPEX.',
  },
  {
    value: '09:50',
    label: '09:50 UK · N2EX day-ahead',
    description: 'GB day-ahead gate closure on N2EX. The 09:30 forecast run is available.',
  },
  {
    value: '11:00',
    label: '11:00 UK · pre-2021 timing',
    legacy: true,
    description:
      'Gate closure before 2021. In this data no forecast run is published between 09:50 and 11:00, so it selects the same run as 09:50.',
  },
];

export function gateFor(value: string): Gate {
  return GATES.find((g) => g.value === value) ?? GATES[0];
}
