/** "Talk" on the session list opens the new session with hands-free already on. */
let want = false;
export const wantAudioChat = () => { want = true; };
export const takeAudioChat = () => { const w = want; want = false; return w; };
