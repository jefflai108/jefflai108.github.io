const debugLink = '<a id="debug-tab" href="https://jefflai108.github.io/debug/">Debug</a>';

// The private snapshot is refreshed independently of this website. Apply the
// site's navigation after installing it, including on scheduled rebuilds.
export function addDebugNavigation(html) {
  let tabsFound = 0;
  const result = html.replace(/<nav\b[^>]*>[\s\S]*?<\/nav>/gi, nav => {
    const opening = nav.slice(0, nav.indexOf('>') + 1);
    const classes = opening.match(/\bclass\s*=\s*(['"])(.*?)\1/i)?.[2].split(/\s+/) || [];
    if (!classes.includes('page-tabs')) return nav;
    tabsFound += 1;

    const benchmark = /<a\b(?=[^>]*\bid\s*=\s*(['"])benchmark-tab\1)[^>]*>[\s\S]*?<\/a>/gi;
    const debug = /<a\b(?=[^>]*\bid\s*=\s*(['"])debug-tab\1)[^>]*>[\s\S]*?<\/a>\s*/gi;
    if ([...nav.matchAll(benchmark)].length !== 1 || [...nav.matchAll(debug)].length > 1) {
      throw new Error('Expected one Benchmark tab and at most one Debug tab in LINE Latest.');
    }
    return nav.replace(debug, '').replace(benchmark, match => `${debugLink}\n        ${match}`);
  });
  if (tabsFound !== 1) throw new Error('Expected one page-tabs navigation in LINE Latest.');
  return result;
}
