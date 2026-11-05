// Assertion text extraction only; output is never used as HTML.
const {execFileSync} = require('node:child_process');
module.exports=html=>execFileSync(process.env.PYTHON || 'python3',['-c',`
from html.parser import HTMLParser
import sys
class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'dialog'}:
            self.hidden += 1
    def handle_endtag(self, tag):
        if tag in {'script', 'dialog'} and self.hidden:
            self.hidden -= 1
    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)
p = VisibleText()
p.feed(sys.stdin.read())
print(' '.join(' '.join(p.parts).split()), end='')
`],{input:html,encoding:'utf8'});
