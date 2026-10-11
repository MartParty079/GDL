"""Generate exact supplied picker chrome; never download mutable dependencies."""
import hashlib
import re
from pathlib import Path
from zipfile import ZipFile

PICKER_SHA256 = '31a55eec94715cc79942e91e172e539e3031dcd5e2e5ee7c1446cf2caee960a6'
NAMES = ('Quiet Workspace', 'Structured Sidebar', 'Command Center')


def build_picker(archive, destination):
    with ZipFile(archive) as bundle:
        raw = bundle.read('skills-main/skills/prototype/PICKER.md')
    if hashlib.sha256(raw).hexdigest() != PICKER_SHA256:
        raise ValueError('The supplied picker specification changed. Review it before rebuilding the harness.')
    source = raw.decode('utf-8')
    markup = re.search(r'```html\n(.*?)\n```', source, re.S)[1]
    styles = re.search(r'```css\n(.*?)\n```', source, re.S)[1]
    script = re.search(r'```js\n(.*?)\n```', source, re.S)[1]
    for old, new in zip(('Quiet', 'Editorial', 'Playful'), NAMES): markup = markup.replace('>' + old + '<', '>' + new + '<')
    # The specification requires omission for static comparisons.
    markup = '\n'.join(line for line in markup.splitlines() if 'proto-picker-divider' not in line and 'proto-picker-replay' not in line)
    bridge = '''
let nativeBridge = null;
let mountedBeforeBridge = false;
const variants = [0, 1, 2].map(i => () => {
  if (nativeBridge) nativeBridge.choose(i);
  else mountedBeforeBridge = true;
  return '';
});
new QWebChannel(qt.webChannelTransport, channel => {
  nativeBridge = channel.objects.pickerBridge;
  if (mountedBeforeBridge) nativeBridge.choose(current);
});
'''
    html = ('<!doctype html><html><head><meta charset="utf-8"><title>Home prototype picker</title>'
            '<style>html,body{margin:0;background:transparent;overflow:hidden}</style><style>' + styles +
            '</style></head><body><div id="stage"></div>' + markup +
            '<script src="qrc:///qtwebchannel/qwebchannel.js"></script><script>' + bridge + script +
            '</script></body></html>')
    destination = Path(destination); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding='utf-8')
    return destination
