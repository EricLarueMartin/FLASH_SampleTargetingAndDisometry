"""Render this note's simple Markdown into an offline HTML companion page."""
from pathlib import Path
import html
import re

root = Path(__file__).resolve().parents[1]
deck = root.parents[1] / "slides" / "2026-11-dosecam-film"
text = (root / "RESEARCH.md").read_text(encoding="utf-8")


def inline(s):
    s = html.escape(s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^\s)]+)\)",
               r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    return s


blocks = re.split(r"\n\s*\n", text.strip())
body, toc = [], []
for b in blocks:
    if b.startswith("#"):
        mark, title = b.split(" ", 1)
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        body.append(f'<h{len(mark)} id="{slug}">{inline(title)}</h{len(mark)}>')
        if len(mark) == 2:
            toc.append(f'<a href="#{slug}">{inline(title)}</a>')
    elif b.startswith("    "):
        body.append("<pre>" + html.escape("\n".join(x[4:] for x in b.splitlines())) + "</pre>")
    elif b.startswith("|"):
        rows = b.splitlines()
        cells = lambda row: row.strip().strip("|").split("|")
        table = '<table><thead><tr>' + ''.join('<th>'+inline(c.strip())+'</th>' for c in cells(rows[0])) + '</tr></thead><tbody>'
        for row in rows[2:]:
            table += '<tr>' + ''.join('<td>'+inline(c.strip())+'</td>' for c in cells(row)) + '</tr>'
        body.append(table+'</tbody></table>')
    elif re.match(r"\d+\. ", b):
        items = re.split(r"\n(?=\d+\. )", b)
        body.append('<ol>'+''.join('<li>'+inline(re.sub(r'^\d+\. ', '', i).replace('\n', ' '))+'</li>' for i in items)+'</ol>')
    else:
        body.append('<p>'+inline(b.replace('\n', ' '))+'</p>')

page = '''<!doctype html><html lang="en" data-theme="day"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>DoseCam research notes</title>
<link rel="stylesheet" href="style.css"><style>
html,body{height:auto;overflow:auto}.notes{max-width:1040px;margin:0 auto;padding:44px 48px 90px 300px;box-sizing:content-box;line-height:1.65;font-size:17px}.notes h1{font-size:32px;line-height:1.2}.notes h2{margin-top:2.5em;line-height:1.3;font-size:26px;scroll-margin-top:25px}.notes h3{font-size:20px;margin-top:2em}.notes a{color:var(--blue)}.notes pre{background:var(--nav);padding:15px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:14px;line-height:1.6}.notes code{font-size:.88em;overflow-wrap:anywhere}.notes table{border-collapse:collapse;width:100%;font-size:15px}.notes td,.notes th{padding:10px;border-bottom:1px solid var(--rule);text-align:left}.notes li{margin-bottom:12px}.outline nav a{font-size:12px}.outline nav{gap:0}.outline nav a{padding:7px 5px}
@media(max-width:900px){.notes{padding-left:220px;padding-right:25px}}@media(max-width:620px){.outline{position:relative;height:auto}.outline nav{display:block}.outline nav a{max-width:none}.outline-bottom{position:static;margin-top:10px}.notes{padding:20px;font-size:16px}.notes h1{font-size:27px}}
</style></head><body><aside class="outline"><a class="brand" href="index.html">← DoseCam slides</a><p class="deck-meta">Research notes<br>16 November 2026</p><nav aria-label="Research outline">'''+''.join(toc)+'''</nav><div class="outline-bottom"><button id="theme-toggle">Night mode</button></div></aside><article class="notes">'''+''.join(body)+'''</article><script>
const button=document.getElementById('theme-toggle');function theme(t){document.documentElement.dataset.theme=t;button.textContent=t==='night'?'Day mode':'Night mode';try{localStorage.setItem('dosecam-deck-theme',t)}catch(e){}}let saved;try{saved=localStorage.getItem('dosecam-deck-theme')}catch(e){}theme(saved||(matchMedia('(prefers-color-scheme: dark)').matches?'night':'day'));button.onclick=()=>theme(document.documentElement.dataset.theme==='night'?'day':'night');
</script></body></html>'''
(deck / "research.html").write_text(page, encoding="utf-8")
print(deck / "research.html")
