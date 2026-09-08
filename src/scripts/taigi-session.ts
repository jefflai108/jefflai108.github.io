/** Shared session and safe tab navigation; credentials remain browser-local. */
export const reviewSession = {
  key: (): string => '',
  ready: (): boolean => false,
  leaveDev: async (): Promise<boolean> => true,
  activeTab: 'dev' as 'dev' | 'record',
};
