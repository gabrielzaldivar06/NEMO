import re, os, base64

base = r'C:\dev\memory persistence\persistent-ai-memory\assets'
icons = {
    'fact':       'icon_book.svg',
    'insight':    'icon_crystal_ball.svg',
    'correction': 'icon_recycle.svg',
    'preference': 'icon_gem_pendant.svg',
    'episodic':   'icon_time_trap.svg',
    'procedure':  'icon_clockwork.svg',
    'skill':      'icon_star.svg',
    'ai_memory':  'icon_brainstorm.svg',
}

results = {}
for t, f in icons.items():
    with open(os.path.join(base, f), encoding='utf-8') as fh:
        c = fh.read()
    # strip black background rect
    c2 = re.sub(r'<path d="M0 0h512v512H0z"/>', '', c)
    # remove hardcoded fill="#fff" so we can set fill via attribute
    c2 = c2.replace(' fill="#fff"', '')
    # extract svg inner
    m = re.search(r'<svg([^>]*)>(.*?)</svg>', c2, re.DOTALL)
    inner = m.group(2).strip().replace('\n', ' ') if m else ''
    # Output as a minimal SVG template with FILL placeholder
    svg_tpl = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" fill="FILL">{inner}</svg>'
    # base64 encode
    b64 = base64.b64encode(svg_tpl.encode('utf-8')).decode('ascii')
    results[t] = b64
    print(f"'{t}': '{b64[:60]}...'  ({len(b64)} b64 chars)")

# Write out JS snippet
js_lines = ['const ICON_B64 = {']
for t, b64 in results.items():
    js_lines.append(f"  {t}: '{b64}',")
js_lines.append('};')
js_out = '\n'.join(js_lines)
with open(r'C:\dev\memory persistence\persistent-ai-memory\assets\icon_data.js', 'w', encoding='utf-8') as fh:
    fh.write(js_out)
print('\nWrote icon_data.js')
