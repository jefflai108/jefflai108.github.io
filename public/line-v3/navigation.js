const tabs = document.querySelector('.benchmark-tabs');
if (tabs) {
  const key = 'line-v3-navigation-scroll';
  try { tabs.scrollLeft = Math.max(0, Number(sessionStorage.getItem(key)) || 0); } catch {}
  const remember = () => {
    try { sessionStorage.setItem(key, String(tabs.scrollLeft)); } catch {}
  };
  tabs.addEventListener('scroll', remember, {passive:true});
  tabs.addEventListener('click', remember);
}
