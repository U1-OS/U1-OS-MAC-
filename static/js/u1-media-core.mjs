// Media links are parsed locally. Never accept arbitrary iframe HTML or script URLs.
export function parseMediaLink(value) {
  const input = String(value || '').trim();
  const uri = input.match(/^spotify:(track|album|playlist|episode|show):([A-Za-z0-9]{22})$/);
  if (uri) return { provider: 'spotify', uri: input, url: `https://open.spotify.com/${uri[1]}/${uri[2]}`, title: `Spotify ${uri[1]}` };
  let url;
  try { url = new URL(input); } catch { throw new Error('Paste a full HTTPS media link, or choose a local file.'); }
  if (url.protocol !== 'https:' || url.username || url.password || (url.port && url.port !== '443')) throw new Error('Use an HTTPS link without embedded credentials or a custom port.');
  const host = url.hostname.toLowerCase();
  if (host === 'open.spotify.com') {
    const match = url.pathname.match(/^\/(?:intl-[a-z-]+\/)?(track|album|playlist|episode|show)\/([A-Za-z0-9]{22})\/?$/);
    if (!match) throw new Error('Use a Spotify track, album, playlist, episode or show link.');
    return {provider:'spotify',uri:`spotify:${match[1]}:${match[2]}`,url:`https://open.spotify.com/${match[1]}/${match[2]}`,title:`Spotify ${match[1]}`};
  }
  if (['youtube.com','www.youtube.com','music.youtube.com','m.youtube.com','youtu.be'].includes(host)) {
    const id = host === 'youtu.be' ? url.pathname.slice(1) : url.searchParams.get('v') || url.pathname.match(/^\/(?:shorts|embed)\/([^/]+)\/?$/)?.[1];
    if (!/^[\w-]{11}$/.test(id || '')) throw new Error('Use a link to one YouTube video or YouTube Music track.');
    return {provider:'youtube',id,url:`https://www.youtube.com/watch?v=${id}`,title:host === 'music.youtube.com' ? 'YouTube Music' : 'YouTube video'};
  }
  if (host === 'soundcloud.com' || host === 'www.soundcloud.com') {
    if (url.pathname.split('/').filter(Boolean).length < 2) throw new Error('Use a SoundCloud track or playlist link, not a profile.');
    return {provider:'soundcloud',url:url.href,title:'SoundCloud track'};
  }
  if (['web.stremio.com','www.stremio.com','stremio.com'].includes(host)) return {provider:'stremio',url:'https://web.stremio.com/',title:'Stremio'};
  if (/\.(mp4|webm|mov|m4v|mp3|m4a|ogg|oga|opus|wav|flac)$/i.test(url.pathname)) {
    return {provider:'direct',url:url.href,title:decodeURIComponent(url.pathname.split('/').pop()),video:/\.(mp4|webm|mov|m4v)$/i.test(url.pathname)};
  }
  throw new Error('Supported: Spotify, YouTube / YouTube Music, SoundCloud, Stremio, or a direct audio/video file. Shortened redirect links must be expanded first.');
}

export function playbackTime(value) {
  const seconds = Number.isFinite(Number(value)) ? Math.max(0, Math.floor(Number(value))) : 0;
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2,'0')}`;
}

export function playbackFraction(position, duration) {
  return Number.isFinite(duration) && duration > 0 ? Math.min(100,Math.max(0,Number(position) / duration * 100 || 0)) : 0;
}
