/** Shared session and safe tab navigation; credentials remain browser-local. */
export const reviewSession = {
  key: (): string => '',
  ready: (): boolean => false,
  leaveDev: async (): Promise<boolean> => true,
  selectDev: async (_tab: 'dev' | 'dev2'): Promise<boolean> => true,
  activeTab: 'dev' as 'dev' | 'dev2' | 'record',
};
