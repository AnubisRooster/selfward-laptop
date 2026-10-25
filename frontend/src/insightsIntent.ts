/** Which part of Insights to open: a button in a session says "dreams" and Insights opens there. */
let want = '';
export const wantInsights = (section: 'highlights' | 'dreams' | 'notes') => { want = section; };
export const takeInsights = () => { const w = want; want = ''; return w; };
