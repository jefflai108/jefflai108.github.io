const tabs = document.querySelector('.benchmark-tabs');
if (tabs) {
  const key = 'line-v3-navigation-scroll';
  try { tabs.scrollLeft = Math.max(0, Number(sessionStorage.getItem(key)) || 0); } catch {}
  // The row scrolls sideways once the tabs outgrow it (always on a phone). A
  // remembered position keeps the bar still while switching tabs, but a
  // direct visit to a later tab would start with that tab off-screen; bring
  // the current tab fully into view only when it is clipped.
  const current = tabs.querySelector('[aria-current="page"]');
  if (current) {
    const row = tabs.getBoundingClientRect(), tab = current.getBoundingClientRect();
    const inset = parseFloat(getComputedStyle(tabs).paddingLeft) || 0;
    if (tab.right > row.right - inset) tabs.scrollLeft += tab.right - row.right + inset;
    else if (tab.left < row.left + inset) tabs.scrollLeft -= row.left + inset - tab.left;
  }
  const remember = () => {
    try { sessionStorage.setItem(key, String(tabs.scrollLeft)); } catch {}
  };
  tabs.addEventListener('scroll', remember, {passive:true});
  tabs.addEventListener('click', remember);
}
